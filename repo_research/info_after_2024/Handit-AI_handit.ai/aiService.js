import Together from "together-ai";
import OpenAI from 'openai';
import { GoogleGenAI, Type } from '@google/genai';
import { BedrockRuntimeClient, InvokeModelCommand } from '@aws-sdk/client-bedrock-runtime';
import { z } from 'zod';
import { zodResponseFormat } from 'openai/helpers/zod';
import axios from 'axios';

function zodSchemaToJson(schema) {
  if (schema instanceof z.ZodString) {
    return '...';
  }
  if (schema instanceof z.ZodNumber) {
    return 0;
  }
  if (schema instanceof z.ZodBoolean) {
    return true;
  }
  if (schema instanceof z.ZodEnum) {
    return schema._def.values[0];
  }
  if (schema instanceof z.ZodArray) {
    return [zodSchemaToJson(schema._def.type)];
  }
  if (schema instanceof z.ZodObject) {
    const shape = schema._def.shape();
    const result = {};
    for (const key in shape) {
      result[key] = zodSchemaToJson(shape[key]);
    }
    return result;
  }
  if (schema instanceof z.ZodOptional || schema instanceof z.ZodNullable) {
    return zodSchemaToJson(schema._def.innerType);
  }
  return null;
}

function zodSchemaToGoogleAI(schema) {
  if (schema instanceof z.ZodString) {
    return { type: Type.STRING };
  }
  if (schema instanceof z.ZodNumber) {
    return { type: Type.NUMBER };
  }
  if (schema instanceof z.ZodBoolean) {
    return { type: Type.BOOLEAN };
  }
  if (schema instanceof z.ZodEnum) {
    return { 
      type: Type.STRING,
      enum: schema._def.values
    };
  }
  if (schema instanceof z.ZodArray) {
    return {
      type: Type.ARRAY,
      items: zodSchemaToGoogleAI(schema._def.type)
    };
  }
  if (schema instanceof z.ZodObject) {
    const shape = schema._def.shape();
    const properties = {};
    const propertyOrdering = [];
    
    for (const key in shape) {
      properties[key] = zodSchemaToGoogleAI(shape[key]);
      propertyOrdering.push(key);
    }
    
    return {
      type: Type.OBJECT,
      properties,
      propertyOrdering
    };
  }
  if (schema instanceof z.ZodOptional || schema instanceof z.ZodNullable) {
    return zodSchemaToGoogleAI(schema._def.innerType);
  }
  return { type: Type.STRING };
}

const DEFAULT_MODEL = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8";

/**
 * Generate response using OpenAI
 */
const generateOpenAIResponse = async ({ messages, responseFormat, token, model, temperature }) => {
  const openai = new OpenAI({
    apiKey: token,
  });
  
  let format = null;

  if (responseFormat) {
    try {
      format = zodResponseFormat(responseFormat, 'responseFormat');
    } catch (error) {
      format = responseFormat;    
    }
  }
  
  const completion = await openai.chat.completions.create({
    model,
    messages,
    response_format: format ? format : null,
    temperature: temperature || 0.7
  });
  
  return completion;
};

/**
 * Generate response using Google AI
 */
const generateGoogleAIResponse = async ({ messages, responseFormat, token, model }) => {
  const genAI = new GoogleGenAI({apiKey: token || process.env.GOOGLE_AI_API_KEY});
  
  // Convert OpenAI messages format to Google AI format
  let prompt = '';
  const systemMessage = messages.find(msg => msg.role === 'system');
  
  if (systemMessage) {
    prompt += systemMessage.content + '\n\n';
  }
  
  // Combine user and assistant messages into a conversation format
  const conversationHistory = [];
  for (let i = 0; i < messages.length; i++) {
    const message = messages[i];
    if (message.role === 'user') {
      const content = message.content;
      if (typeof content === 'object') {
        conversationHistory.push(`User: ${JSON.stringify(content)}`);
      } else {
        conversationHistory.push(`User: ${content}`);
      }
    } else if (message.role === 'assistant') {
      const content = message.content;
      if (typeof content === 'object') {
        conversationHistory.push(`Assistant: ${JSON.stringify(content)}`);
      } else {
        conversationHistory.push(`Assistant: ${content}`);
      }
    }
  }
  
  prompt += conversationHistory.join('\n');
  
  // Build config for structured output
  const config = {};
  if (responseFormat) {
    const googleAISchema = zodSchemaToGoogleAI(responseFormat);
    config.responseMimeType = "application/json";
    config.responseSchema = googleAISchema;
  }
  
  const result = await genAI.models.generateContent({
    model: model || 'gemini-1.5-flash',
    contents: prompt,
    config: Object.keys(config).length > 0 ? config : undefined,
  });
  
  // Format response to match OpenAI structure
  return {
    choices: [{
      message: {
        content: result.text,
        role: 'assistant'
      },
      finish_reason: 'stop'
    }],
    usage: {
      prompt_tokens: 0, // Google AI doesn't provide token counts in the same way
      completion_tokens: 0,
      total_tokens: 0
    }
  };
};

/**
 * Generate response using Together AI
 */
const generateTogetherAIResponse = async ({ messages, responseFormat, token, model }) => {
  const together = new Together({
    apiKey: token,
  });
  
  const responseFormatJson = zodSchemaToJson(responseFormat);
  if (responseFormatJson) {
    messages.push({
      role: 'user',
      content: `You must response in the following format: ${JSON.stringify(responseFormatJson, null, 2)} and you should not include any other text or comments`
    });
    const system = messages.find(message => message.role === 'system');
    system.content = system.content + `\n\nYou must response in the following format: ${JSON.stringify(responseFormatJson, null, 2)} and you should not include any other text or comments`;
    messages[0] = system;
  }
  
  return await together.chat.completions.create({
    model,
    messages,
  });
};

/**
 * Generate response using AWS Bedrock
 */
const generateAWSBedrockResponse = async ({ messages, responseFormat, tokenData, model, token = null }) => {
  // Handle structured output format like Together AI
  const responseFormatJson = zodSchemaToJson(responseFormat);
  let modifiedMessages = [...messages];
  
  if (responseFormatJson) {
    // Add format instructions to the system message
    const systemMessage = modifiedMessages.find(msg => msg.role === 'system');
    if (systemMessage) {
      systemMessage.content = systemMessage.content + `\n\nYou must respond in the following JSON format: ${JSON.stringify(responseFormatJson, null, 2)} and you should not include any other text or comments outside of this JSON structure.`;
    } else {
      // Add system message if none exists
      modifiedMessages.unshift({
        role: 'system',
        content: `You must respond in the following JSON format: ${JSON.stringify(responseFormatJson, null, 2)} and you should not include any other text or comments outside of this JSON structure.`
      });
    }
  }
  
  // Convert messages to Bedrock format
  let prompt = '';
  const systemMessage = modifiedMessages.find(msg => msg.role === 'system');
  
  if (systemMessage) {
    prompt += systemMessage.content + '\n\n';
  }
  
  // Add conversation history
  for (let i = 0; i < modifiedMessages.length; i++) {
    const message = modifiedMessages[i];
    if (message.role === 'user') {
      prompt += `Human: ${message.content}\n\n`;
    } else if (message.role === 'assistant') {
      prompt += `Assistant: ${message.content}\n\n`;
    }
  }
  
  // Prepare the request body based on the model
  let body;
  if (model.includes('claude')) {
    body = {
      "anthropic_version": "bedrock-2023-05-31", 
      "max_tokens": 1024,
      "messages": modifiedMessages.map(message => ({
        role: message.role === 'user' ? 'user' : 'assistant',
        content: message.content
      }))
    };
  } else if (model.includes('titan')) {
    body = {
      inputText: prompt,
      textGenerationConfig: {
        maxTokenCount: 1000,
        temperature: 0.7,
        topP: 0.9,
      },
    };
  } else {
    // Default format for other models
    body = {
      prompt: prompt,
      max_tokens: 1000,
      temperature: 0.7,
    };
  }

  let responseBody;
  
  // Check if we're using API key or AWS credentials
  if (!tokenData?.accessKeyId) {
    // Use API key authentication with HTTP call
    const region = tokenData?.region || 'us-west-2';
    const url = `https://bedrock-runtime.${region}.amazonaws.com/model/${model}/invoke`;
    
    try {
      const response = await axios.post(url, body, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      responseBody = response.data;
    } catch (error) {
      console.error('Bedrock API call failed:', error.response?.data || error.message);
      throw new Error(`Bedrock API call failed: ${error.response?.data?.message || error.message}`);
    }
  } else {
    // Use AWS credentials with SDK
    const { accessKeyId, secretAccessKey, region, sessionToken } = tokenData;
    
    if (!accessKeyId || !secretAccessKey) {
      throw new Error('AWS credentials (accessKeyId and secretAccessKey) are required when not using API key');
    }
    
    const client = new BedrockRuntimeClient({
      region: region || 'us-east-1',
      credentials: {
        accessKeyId,
        secretAccessKey,
        sessionToken, // optional
      },
    });
    
    const command = new InvokeModelCommand({
      modelId: model,
      contentType: 'application/json',
      accept: 'application/json',
      body: JSON.stringify(body),
    });
    
    const response = await client.send(command);
    responseBody = JSON.parse(new TextDecoder().decode(response.body));
  }
  
  // Parse response based on model type
  let text;
  if (model.includes('claude')) {
    text = responseBody.content[0].text;
  } else if (model.includes('titan')) {
    text = responseBody.results[0].outputText;
  } else {
    text = responseBody.text || responseBody.completion || responseBody.generated_text;
  }
  
  // Format response to match OpenAI structure
  return {
    choices: [{
      message: {
        content: text,
        role: 'assistant'
      },
      finish_reason: 'stop'
    }],
    usage: {
      prompt_tokens: 0, // AWS Bedrock doesn't provide token counts in the same way
      completion_tokens: 0,
      total_tokens: 0
    }
  };
};

/**
 * Generates text using various AI providers
 * @param {Object} params - The parameters for text generation
 * @param {Array} params.messages - Array of message objects with role and content
 * @param {string} params.model - Optional model override
 * @param {string} params.provider - AI provider to use
 * @param {string} params.token - API token (for simple providers)
 * @param {Object} params.tokenData - Token data object (for complex providers like AWS)
 * @param {Object} params.responseFormat - Zod schema for structured output
 * @param {boolean} params.isN8N - Whether this is an N8N request
 * @returns {Promise<Object>} The generated text and metadata
 */
export const generateAIResponse = async ({
  messages,
  responseFormat = null,
  token = process.env.TOGETHER_API_KEY,
  tokenData = null,
  model = DEFAULT_MODEL,
  provider = 'TogetherAI',
  isN8N = false,
  temperature = 0.7,
}) => {
  try {
    let completion;

    if (isN8N) {
      provider = 'TogetherAI';
      model = DEFAULT_MODEL;
      token = process.env.TOGETHER_API_KEY;
    }

    switch (provider) {
      case 'OpenAI':
        completion = await generateOpenAIResponse({ messages, responseFormat, token, model, temperature });
        break;
        
      case 'GoogleAI':
        completion = await generateGoogleAIResponse({ messages, responseFormat, token, model });
        break;
        
      case 'TogetherAI':
        completion = await generateTogetherAIResponse({ messages, responseFormat, token, model });
        break;
        
      case 'AWSBedrock':
        console.log('tokenData', tokenData);
        console.log('token', token);
        if (!tokenData && !token) {
          throw new Error('AWS Bedrock requires tokenData with AWS credentials or token');
        }
        completion = await generateAWSBedrockResponse({ messages, responseFormat, tokenData: tokenData || {}, model, token });
        break;
        
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }

    return {
      ...completion,
      text: completion.choices[0].message.content,
      usage: completion.usage,
      finishReason: completion.choices[0].finish_reason
    };
  } catch (error) {
    console.error("Error generating AI response:", error);
    throw error;
  }
};

/**
 * Streams text using the Together AI API
 * @param {Object} params - The parameters for text streaming
 * @param {Array} params.messages - Array of message objects with role and content
 * @param {string} params.model - Optional model override
 * @param {Object} params.config - Optional configuration parameters
 * @returns {AsyncGenerator} A stream of text chunks
 */
export const streamAIResponse = async function* ({
  messages,
  model = DEFAULT_MODEL,
  config = {}
}) {
  try {
    const together = new Together({
      apiKey: process.env.TOGETHER_API_KEY,
    });
    
    const stream = await together.chat.completions.create({
      model,
      messages,
      temperature: config.temperature || 0.7,
      top_p: config.topP || 0.95,
      max_tokens: config.maxTokens || 1000,
      presence_penalty: config.presencePenalty || 0,
      frequency_penalty: config.frequencyPenalty || 0,
      stream: true
    });

    let usage;
    for await (const chunk of stream) {
      if (chunk.choices[0].finish_reason) {
        usage = chunk.usage;
      } else {
        yield chunk.choices[0].delta.content;
      }
    }

    return {
      usage,
      finishReason: 'stop'
    };
  } catch (error) {
    console.error("Error streaming AI response:", error);
    throw error;
  }
};

/**
 * Example tool definitions for structured output
 */
export const structuredOutputTools = {
  extractEntities: {
    type: "function",
    function: {
      name: "extractEntities",
      description: "Extract named entities from text",
      parameters: {
        type: "object",
        properties: {
          entities: {
            type: "array",
            items: {
              type: "object",
              properties: {
                text: { type: "string" },
                type: { type: "string", enum: ["PERSON", "ORG", "LOC", "DATE"] },
                confidence: { type: "number" }
              }
            }
          }
        }
      }
    }
  },
  classifyContent: {
    type: "function",
    function: {
      name: "classifyContent",
      description: "Classify content into predefined categories",
      parameters: {
        type: "object",
        properties: {
          category: {
            type: "string",
            enum: ["BUSINESS", "TECH", "HEALTH", "OTHER"]
          },
          confidence: { type: "number" },
          subCategories: {
            type: "array",
            items: { type: "string" }
          }
        }
      }
    }
  },
  analyzeImage: {
    type: "function",
    function: {
      name: "analyzeImage",
      description: "Analyze image content and provide structured description",
      parameters: {
        type: "object",
        properties: {
          objects: {
            type: "array",
            items: { type: "string" }
          },
          scene: { type: "string" },
          actions: {
            type: "array",
            items: { type: "string" }
          },
          emotions: {
            type: "array",
            items: { type: "string" }
          }
        }
      }
    }
  }
};
