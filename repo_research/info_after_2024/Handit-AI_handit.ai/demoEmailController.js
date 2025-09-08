import { emailAgent } from '../demo/emailAgent/index.js';
import { singleEvaluate } from '../services/evaluationService.js';
import db from '../../models/index.js';
import { reviewEntry, runReview } from '../services/insightsService.js';
import { enhancePrompt } from '../services/promptEnhancementService.js';
const { ModelLog, Model } = db;

export const generateEmail = async (req, res) => {
  try {
    const { text, prompt = null, optimized = false } = req.body;

    if (!text) {
      return res.status(400).json({
        error: 'Text input is required'
      });
    }

    // Get the first node (preprocess)
    const firstNode = await emailAgent.config.nodes.find(node => node.initialNode);
    if (!firstNode) {
      return res.status(500).json({
        error: 'No initial node found in agent configuration'
      });
    }

    // Execute the agent flow
    const result = await emailAgent.execute({
      input: text,
      environment: 'production',
      prompt: prompt,
      optimized: optimized
    });

    

    return res.json(result);
  } catch (error) {
    console.error('Error generating email:', error);
    return res.status(500).json({
      error: error.message || 'Failed to generate email'
    });
  }
}; 

export const evaluateEmail = async (req, res) => {
  const { modelLogId } = req.body;

  const modelLog = await ModelLog.findByPk(modelLogId);

  const evaluator = await Model.findOne({
    where: {
      id: 256
    }
  });
  
  
  const result = await singleEvaluate(modelLog, evaluator);

  return res.json(result);
};

export const generateInsight = async (req, res) => {
  const { modelLogId } = req.body;

  const modelLog = await ModelLog.findByPk(modelLogId);
  const reviewer = await Model.findOne({
    where: {
      id: 257
    }
  });
  const insight = await reviewEntry(
    modelLog,
    reviewer,
    ModelLog,
    [],
    'demo'
  )

  return res.json(insight);
}

export const enhancePromptFunc = async (req, res) => {
  const originalPrompt = 'Just generate an email in Spanish with the following details:'
  const { suggestions } = req.body;

  const enhancedPrompt = await enhancePrompt(originalPrompt, suggestions);

  return res.json(enhancedPrompt);
}