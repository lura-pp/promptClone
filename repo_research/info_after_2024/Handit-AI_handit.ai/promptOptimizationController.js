/**
 * @fileoverview Prompt Optimization Controller
 * 
 * This controller provides endpoints for testing and managing prompt optimizations.
 * It allows manual triggering of GitHub PR creation for prompt improvements.
 * 
 * Features:
 * - Test PR creation endpoint
 * - Manual prompt optimization trigger
 * - Validation and error handling
 * 
 * @example
 * POST /api/prompt-optimization/test-pr
 * {
 *   "agentId": 123,
 *   "originalPrompt": "You are a helpful assistant...",
 *   "optimizedPrompt": "You are an expert assistant that...",
 *   "metrics": { "improvement": 0.15, "accuracy": 0.92 }
 * }
 */

import { createPromptOptimizationPR } from '../services/promptOptimizationPRService.js';
import { parseContext } from '../services/parser.js';
import db from '../../models/index.js';

const { Agent, Company, GitHubIntegration, GitHubPullRequest } = db;

/**
 * Tests the prompt optimization PR creation process
 * 
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @returns {Promise<void>}
 */
export const testPromptOptimizationPR = async (req, res) => {
  try {
    console.log('🧪 Testing prompt optimization PR creation...');
    
    const { agentId, originalPrompt, optimizedPrompt, metrics = {} } = req.body;

    // Validation
    if (!agentId) {
      return res.status(400).json({
        success: false,
        error: 'agentId is required'
      });
    }

    if (!originalPrompt || !optimizedPrompt) {
      return res.status(400).json({
        success: false,
        error: 'Both originalPrompt and optimizedPrompt are required'
      });
    }

    if (originalPrompt === optimizedPrompt) {
      return res.status(400).json({
        success: false,
        error: 'originalPrompt and optimizedPrompt cannot be the same'
      });
    }

    // Find the agent
    const agent = await Agent.findByPk(agentId);
    if (!agent) {
      return res.status(404).json({
        success: false,
        error: `Agent with ID ${agentId} not found`
      });
    }

    // Check if agent has repository configured
    if (!agent.repository) {
      return res.status(400).json({
        success: false,
        error: `Agent "${agent.name}" does not have a repository URL configured`
      });
    }

    // Default metrics if not provided
    const defaultMetrics = {
      accuracy: 0.85,
      improvement: 0.15,
      totalEvaluations: 100,
      successfulEvaluations: 85,
      timestamp: new Date().toISOString(),
      ...metrics
    };

    console.log(`📋 Creating PR for Agent: ${agent.name} (ID: ${agentId})`);
    console.log(`📁 Repository: ${agent.repository}`);
    console.log(`📊 Metrics: ${JSON.stringify(defaultMetrics, null, 2)}`);

    // Create the PR
    const result = await createPromptOptimizationPR({
      agent,
      originalPrompt: originalPrompt.trim(),
      optimizedPrompt: optimizedPrompt.trim(),
      metrics: defaultMetrics,
      models: db
    });

    // Return the result
    res.status(result.success ? 200 : 400).json({
      success: result.success,
      message: result.success 
        ? `Successfully created GitHub PR for prompt optimization`
        : `Failed to create GitHub PR: ${result.error}`,
      data: result.success ? {
        prNumber: result.prNumber,
        prUrl: result.prUrl,
        branchName: result.branchName,
        filesChanged: result.filesChanged,
        locationsFound: result.locationsFound,
        agent: {
          id: agent.id,
          name: agent.name,
          repository: agent.repository
        },
        metrics: defaultMetrics
      } : null,
      error: result.success ? null : result.error,
      debug: {
        agentId,
        hasRepository: !!agent.repository,
        originalPromptLength: originalPrompt.length,
        optimizedPromptLength: optimizedPrompt.length,
        metricsProvided: Object.keys(metrics).length > 0
      }
    });

  } catch (error) {
    console.error('❌ Error in testPromptOptimizationPR:', error);
    
    res.status(500).json({
      success: false,
      message: 'Internal server error while testing prompt optimization PR',
      error: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
};

/**
 * Gets the status of recent prompt optimization PRs for an agent
 * 
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @returns {Promise<void>}
 */
export const getPromptOptimizationStatus = async (req, res) => {
  try {
    const { agentId } = req.params;

    // Find the agent
    const agent = await Agent.findByPk(agentId);
    if (!agent) {
      return res.status(404).json({
        success: false,
        error: `Agent with ID ${agentId} not found`
      });
    }

    // Get company and GitHub integration
    const company = await Company.findByPk(agent.companyId);
    const githubIntegration = await GitHubIntegration.findOne({
      where: {
        companyId: company.id,
        active: true
      }
    });

    // Get recent PRs for this agent
    const recentPRs = await GitHubPullRequest.findAll({
      where: {
        modelId: agentId // Using agent ID as model reference
      },
      order: [['createdAt', 'DESC']],
      limit: 10
    });

    res.json({
      success: true,
      data: {
        agent: {
          id: agent.id,
          name: agent.name,
          repository: agent.repository,
          hasRepository: !!agent.repository
        },
        company: {
          id: company.id,
          name: company.name
        },
        githubIntegration: githubIntegration ? {
          id: githubIntegration.id,
          active: githubIntegration.active,
          tokenExpired: githubIntegration.isTokenExpired(),
          repositoryOwner: githubIntegration.repositoryOwner,
          repositoryName: githubIntegration.repositoryName
        } : null,
        recentPRs: recentPRs.map(pr => ({
          id: pr.id,
          prNumber: pr.prNumber,
          prUrl: pr.prUrl,
          status: pr.status,
          metricsImprovement: pr.metricsImprovement,
          createdAt: pr.createdAt
        })),
        canCreatePR: !!(agent.repository && githubIntegration && !githubIntegration.isTokenExpired())
      }
    });

  } catch (error) {
    console.error('❌ Error in getPromptOptimizationStatus:', error);
    
    res.status(500).json({
      success: false,
      message: 'Internal server error while getting prompt optimization status',
      error: error.message
    });
  }
};

/**
 * Lists all agents with their repository configuration status
 * 
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @returns {Promise<void>}
 */
export const listAgentsWithRepositories = async (req, res) => {
  try {
    // Get user's company from auth middleware
    const companyId = req.user?.companyId;
    if (!companyId) {
      return res.status(401).json({
        success: false,
        error: 'Company ID not found in user context'
      });
    }

    // Find all agents for the company
    const agents = await Agent.findAll({
      where: {
        companyId,
        deletedAt: null
      },
      order: [['name', 'ASC']]
    });

    // Get GitHub integration status
    const githubIntegration = await GitHubIntegration.findOne({
      where: {
        companyId,
        active: true
      }
    });

    const agentsWithStatus = agents.map(agent => ({
      id: agent.id,
      name: agent.name,
      repository: agent.repository,
      hasRepository: !!agent.repository,
      canCreatePR: !!(agent.repository && githubIntegration && !githubIntegration.isTokenExpired()),
      createdAt: agent.createdAt
    }));

    res.json({
      success: true,
      data: {
        agents: agentsWithStatus,
        totalAgents: agents.length,
        agentsWithRepositories: agentsWithStatus.filter(a => a.hasRepository).length,
        githubIntegration: githubIntegration ? {
          active: githubIntegration.active,
          tokenExpired: githubIntegration.isTokenExpired()
        } : null
      }
    });

  } catch (error) {
    console.error('❌ Error in listAgentsWithRepositories:', error);
    
    res.status(500).json({
      success: false,
      message: 'Internal server error while listing agents',
      error: error.message
    });
  }
};