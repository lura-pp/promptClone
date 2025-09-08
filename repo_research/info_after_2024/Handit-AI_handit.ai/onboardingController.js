import { generateAIResponse } from '../services/aiService.js';
import { z } from 'zod';
import db from '../../models/index.js';

// Define the Zod schema for the structured output
const SetupStepSchema = z.object({
  title: z.string(),
  description: z.string(),
  code: z.string().optional()
});

const SetupGuideSchema = z.object({
  title: z.string(),
  description: z.string(),
  steps: z.array(SetupStepSchema)
});

// Handit documentation content
const HANDIT_DOCS = `
# HandIt Tracing Quickstart

## Installation

### JavaScript/Node.js
\`\`\`bash
npm install @handit.ai/node
\`\`\`

### Python
\`\`\`bash
pip install handit-sdk
\`\`\`

## Configuration

### JavaScript
\`\`\`javascript
import { config } from '@handit.ai/node';

config({
  apiKey: 'your-api-key',  // Required: your API key
});
\`\`\`

### Python
\`\`\`python
from handit import HanditTracker

tracker = HanditTracker()
tracker.config(api_key="your-api-key")
\`\`\`

## Basic Usage

### JavaScript - Manual Node Tracking
\`\`\`javascript
import { startTracing, trackNode, endTracing } from '@handit.ai/node';

async function processUserRequest(userId, actionType) {
  // Start a trace session
  const tracingResponse = await startTracing({ 
    agentName: 'ecommerce_agent' 
  });
  const executionId = tracingResponse.executionId;

  try {
    // Step 1: Authenticate user (tool node)
    const userAuth = await authenticateUser(userId);
    // Track AFTER getting the output
    await trackNode({
      input: { userId, actionType },
      output: userAuth,
      nodeName: 'user_authentication',
      agentName: 'ecommerce_agent',
      nodeType: 'tool',
      executionId
    });

    // Step 2: Generate AI response (LLM node)
    const llmResponse = await openai.chat.completions.create({
      messages: [
        { role: "system", content: "You are a helpful ecommerce assistant." },
        { role: "user", content: \`Help user with: \${actionType}\` }
      ],
      model: "gpt-4"
    });
    
    // Track AFTER getting the LLM output
    await trackNode({
      input: {
        systemPrompt: "You are a helpful ecommerce assistant.",
        userPrompt: \`Help user with: \${actionType}\`,
        userId: userId,
        // You can add any additional data here
        temperature: 0.7,
        model: "gpt-4"
      },
      output: llmResponse.choices[0].message.content,
      nodeName: 'ai_response_generator',
      agentName: 'ecommerce_agent',
      nodeType: 'llm',
      executionId
    });

    return llmResponse.choices[0].message.content;
  } finally {
    // End the trace session
    await endTracing({ executionId, agentName: 'ecommerce_agent' });
  }
}
\`\`\`

### Python - Manual Node Tracking
\`\`\`python
from handit_service import tracker
import openai

async def process_user_request(user_id: str, action_type: str):
    # Start a trace session
    tracing_response = await tracker.start_tracing(agent_name="customer_service_agent")
    execution_id = tracing_response["execution_id"]
    
    try:
        # Step 1: Authenticate user (tool node)
        user_auth = await authenticate_user(user_id)
        # Track AFTER getting the output
        tracker.track_node(
            input={"user_id": user_id, "action_type": action_type},
            output=user_auth,
            node_name="user_authentication",
            agent_name="customer_service_agent",
            node_type="tool",
            execution_id=execution_id
        )
        
        # Step 2: Generate AI response (LLM node)
        system_prompt = "You are a helpful customer service assistant."
        user_prompt = f"Help customer with: {action_type}"
        
        llm_response = await openai.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4"
        )
        
        # Track AFTER getting the LLM output
        tracker.track_node(
            input={
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "user_id": user_id,
                # You can add any additional data here
                "temperature": 0.7,
                "model": "gpt-4",
                "context": user_auth
            },
            output=llm_response.choices[0].message.content,
            node_name="response_generator",
            agent_name="customer_service_agent",
            node_type="llm",
            execution_id=execution_id
        )
        
        return llm_response.choices[0].message.content
    finally:
        # End the trace session
        await tracker.end_tracing(execution_id=execution_id, agent_name="customer_service_agent")
\`\`\`

## Advanced Usage

### When to Track Nodes

**Important**: Track nodes AFTER getting the output, not before. The tracking captures the complete input→output flow.

**LLM Nodes** (AI model calls):
\`\`\`python
# Call the LLM first
response = await openai.chat.completions.create(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"}
    ],
    model="gpt-4"
)

# Then track with separated prompts
tracker.track_node(
    input={
        "system_prompt": "You are a helpful assistant.",
        "user_prompt": "What is Python?",
        "model": "gpt-4",
        "temperature": 0.7,
        # Add any additional context or parameters
        "conversation_id": "conv_123"
    },
    output=response.choices[0].message.content,
    node_name="gpt4_response",
    agent_name="my_agent",
    node_type="llm",
    execution_id=execution_id
)
\`\`\`

**Tool Nodes** (Function calls, API calls, database queries):
\`\`\`python
# Execute the tool first
search_results = await database.search(query)

# Then track the results
tracker.track_node(
    input={
        "query": search_query,
        "filters": {"category": "tech"},
        "limit": 10
    },
    output=search_results,
    node_name="database_search",
    agent_name="my_agent",
    node_type="tool",
    execution_id=execution_id
)
\`\`\`

### Tracking Errors
\`\`\`python
try:
    # Execute the operation first
    result = await process_data(input_data)
    
    # Track successful result
    tracker.track_node(
        input={"data": input_data, "operation": "process"},
        output=result,
        node_name="data_processor",
        agent_name="my_agent",
        node_type="tool",
        execution_id=execution_id
    )
except Exception as error:
    # Track the error as output
    tracker.track_node(
        input={"data": input_data, "operation": "process"},
        output={"error": str(error), "error_type": type(error).__name__},
        node_name="data_processor",
        agent_name="my_agent",
        node_type="tool",
        execution_id=execution_id
    )
\`\`\`

### Best Practices

1. **Track AFTER getting output** - Execute the operation first, then track the result
2. **Separate system and user prompts** - Use distinct fields for system_prompt and user_prompt
3. **Include additional context** - Add relevant parameters, IDs, and metadata to input
4. **Use unique node_name values** for different operations
5. **Use descriptive agent_name** to identify your application
6. **Always end tracing sessions** to complete the trace
7. **Track errors as output** - Still track when operations fail
`;

/**
 * Generate personalized setup instructions based on user's answers
 */
export const generatePersonalizedSetup = async (req, res) => {
  const startTime = Date.now();
  
  try {
    const { useCase, language, agentDescription, apiToken } = req.body;

    // Validate required fields
    if (!useCase || !language || !agentDescription) {
      return res.status(400).json({
        error: 'Missing required fields: useCase, language, and agentDescription are required'
      });
    }

    // Replace placeholder API keys with the user's actual API token
    const personalizedDocs = HANDIT_DOCS.replace(/your-api-key/g, apiToken || 'your-api-key');

    // Create personalized prompt for AI
    const prompt = `
You are a technical documentation expert helping developers quickly integrate HandIt AI monitoring into their projects.

Based on the following information about the user's project:
- **Use Case**: ${useCase}
- **Language/Framework**: ${language}
- **Agent Description**: ${agentDescription}
${apiToken ? `- **API Key**: ${apiToken} (use this exact key in all code examples)` : ''}

Using the HandIt documentation provided below, generate a focused, quick setup guide.

Create 3-4 essential steps that include:
1. **Installation** - Specific to their language/framework
2. **Configuration** - With their API key setup ${apiToken ? '(use the provided API key)' : ''}
3. **Implementation** - Core tracking setup tailored to their agent description

Make each step:
- **Specific** to their use case and language
- **Practical** with working code examples ${apiToken ? 'using the provided API key' : ''}
- **Clear** and **concise** with good descriptions
- **Actionable** with concrete instructions
- **Focused** on getting them connected quickly

${apiToken ? 'IMPORTANT: Use the exact API key provided in all code examples - do not use placeholder text.' : ''}

Here's the HandIt documentation to reference:

${personalizedDocs}

Generate a quick setup guide with a descriptive title, brief overview, and essential steps with code examples.
`;

    const completion = await generateAIResponse({
      messages: [
        {
          role: "system",
          content: "You are a helpful technical documentation expert specializing in AI monitoring and tracing systems."
        },
        {
          role: "user",
          content: prompt
        }
      ],
      responseFormat: SetupGuideSchema
    });

    const personalizedGuide = JSON.parse(completion.choices[0].message.content);

    // Return the structured guide
    res.json({
      success: true,
      guide: personalizedGuide,
      metadata: {
        useCase,
        language,
        agentDescription,
        apiTokenIncluded: !!apiToken,
        generatedAt: new Date().toISOString(),
        processingTime: Date.now() - startTime
      }
    });

  } catch (error) {
    console.error('Error generating personalized setup:', error);
    res.status(500).json({
      error: 'Failed to generate personalized setup instructions',
      details: error.message
    });
  }
};

/**
 * Test connection by checking if the company has at least one agent
 */

export const testConnectionCLI = async (req, res) => {
  try {
    // Get company ID from various sources (auth middleware sets different properties)
    const companyId = 
      req.company?.id ||           // API token auth
      req.userObject?.companyId || // JWT auth
      req.user?.companyId ||       // Fallback
      req.body.companyId ||        // Request body
      req.params.companyId;        // URL params

    const agentName = req.body.agentName;
    
    if (!companyId) {
      return res.status(400).json({
        success: false,
        error: 'Company ID is required. Please ensure you are authenticated.'
      });
    }

    // Check if the company has at least one agent
    const agentCount = await db.Agent.count({
      where: {
        company_id: companyId,
        deleted_at: null, // Only count non-deleted agents
        name: agentName
      }
    });

    const hasAgents = agentCount > 0;

    res.json({
      success: true,
      connected: hasAgents,
      agentCount: agentCount,
      message: hasAgents 
        ? `Connection successful! Found ${agentCount} agent${agentCount > 1 ? 's' : ''} connected to HandIt.`
        : 'No agents connected yet. Please follow the setup instructions to connect your first agent.'
    });

  } catch (error) {
    console.error('Error testing connection:', error);
    res.status(500).json({
      success: false,
      connected: false,
      error: 'Failed to test connection',
      details: error.message
    });
  }
};
export const testConnection = async (req, res) => {
  try {
    // Get company ID from various sources (auth middleware sets different properties)
    const companyId = 
      req.company?.id ||           // API token auth
      req.userObject?.companyId || // JWT auth
      req.user?.companyId ||       // Fallback
      req.body.companyId ||        // Request body
      req.params.companyId;        // URL params
    
    if (!companyId) {
      return res.status(400).json({
        success: false,
        error: 'Company ID is required. Please ensure you are authenticated.'
      });
    }

    // Check if the company has at least one agent
    const agentCount = await db.Agent.count({
      where: {
        company_id: companyId,
        deleted_at: null // Only count non-deleted agents
      }
    });

    const hasAgents = agentCount > 0;

    res.json({
      success: true,
      connected: hasAgents,
      agentCount: agentCount,
      message: hasAgents 
        ? `Connection successful! Found ${agentCount} agent${agentCount > 1 ? 's' : ''} connected to HandIt.`
        : 'No agents connected yet. Please follow the setup instructions to connect your first agent.'
    });

  } catch (error) {
    console.error('Error testing connection:', error);
    res.status(500).json({
      success: false,
      connected: false,
      error: 'Failed to test connection',
      details: error.message
    });
  }
}; 