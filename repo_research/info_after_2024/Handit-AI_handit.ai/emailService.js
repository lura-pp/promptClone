// services/emailService.js
import sgMail from '@sendgrid/mail';
import path from 'path';
import fs from 'fs';
import handlebars from 'handlebars';
import dotenv from 'dotenv';
import { Op } from 'sequelize';

dotenv.config();

const __dirname = path.resolve();
// Set SendGrid API Key
sgMail.setApiKey(process.env.SENDGRID_API_KEY);

/**
 * Renders an HTML template with provided data.
 * @param {string} templateName - Name of the template file (without extension).
 * @param {Object} data - Data to inject into the template.
 * @returns {string} - Rendered HTML.
 */
const renderTemplate = (templateName, data) => {
  const filePath = path.join(
    __dirname,
    'src',
    'services',
    'templates',
    `${templateName}.hbs`
  );
  const source = fs.readFileSync(filePath, 'utf8');
  const template = handlebars.compile(source);
  return template(data);
};

/**
 * Sends an email.
 * @param {Object} options - Email options.
 * @param {string} options.to - Recipient email address.
 * @param {string} options.subject - Email subject.
 * @param {string} options.text - Plain text body.
 * @param {string} [options.html] - HTML body.
 * @param {Array} [options.attachments] - Array of attachment objects.
 * @param {string} [options.notificationSource] - Source of the notification (e.g., agent_node, model_log).
 * @param {number} [options.sourceId] - ID of the source (e.g., agent_node_id, model_log_id).
 * @returns {Promise<void>}
 */
export const sendEmail = async ({
  to,
  subject,
  text,
  html,
  attachments,
  Email,
  User,
  notificationSource,
  sourceId,
}) => {
  // If this is a notification email, check rate limiting
  if (notificationSource && sourceId) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Count notifications from the same source today
    const todayNotifications = await Email.count({
      where: {
        notificationSource,
        sourceId,
        createdAt: {
          [Op.gte]: today,
        },
      },
    });

    // If we've already sent 2 notifications from this source today, skip
    /*if (todayNotifications >= 2) {
      console.log(`Rate limit reached for notifications from source ${notificationSource} with ID ${sourceId}`);
      return;
    }*/
  }

  const msg = {
    to,
    from: {
      email: process.env.EMAIL_FROM, // contact@handit.ai
      name: 'Handit.AI',
    },
    subject,
    text,
    html,
    attachments,
  };

  try {
    await sgMail.send(msg);

    // Save email to database
    await Email.create({
      to: to instanceof Array ? to.join(',') : to,
      from: process.env.EMAIL_FROM,
      subject,
      body: text,
      html,
      attachments: JSON.stringify(attachments),
      status: 'sent',
      sentAt: new Date(),
      notificationSource,
      sourceId,
    });
    console.log(`Email sent to ${to}`);
  } catch (error) {
    console.error(`Error sending email to ${to}:`, error);
    if (error.response) {
      console.error(error.response.body);
    }
    await Email.create({
      to,
      from: process.env.EMAIL_FROM,
      subject,
      body: text,
      html,
      attachments: JSON.stringify(attachments),
      status: 'failed',
      notificationSource,
      sourceId,
    });
    throw error;
  }
};

/**
 * Sends a bulk email.
 * @param {Object} options - Bulk email options.
 * @param {Array<string>} options.recipients - Array of recipient email addresses.
 * @param {string} options.subject - Email subject.
 * @param {string} options.text - Plain text body.
 * @param {string} [options.html] - HTML body.
 * @returns {Promise<void>}
 */
export const sendBulkEmail = async ({ recipients, subject, text, html }) => {
  const msg = {
    to: recipients,
    from: {
      email: process.env.EMAIL_FROM, // contact@handit.ai
      name: 'Handit.AI',
    },
    subject,
    text,
    html,
  };

  try {
    await sgMail.send(msg);
    console.log(`Bulk email sent to ${recipients.length} recipients`);
  } catch (error) {
    console.error('Error sending bulk email:', error);
    if (error.response) {
      console.error(error.response.body);
    }
    throw error;
  }
};

/**
 * Sends a templated email.
 * @param {Object} options - Email options.
 * @param {string} options.to - Recipient email address.
 * @param {string} options.subject - Email subject.
 * @param {Object} options.templateData - Data for the template.
 * @param {string} options.templateName - Name of the template file (without extension).
 * @param {Array} [options.attachments] - Array of attachment objects.
 * @returns {Promise<void>}
 */
export const sendTemplatedEmail = async ({
  to,
  subject,
  templateName,
  templateData,
  attachments,
  Email,
  User,
  notificationSource,
  sourceId,
}) => {
  const html = renderTemplate(templateName, templateData);
  console.log(html);

  await sendEmail({
    to,
    subject,
    text: 'This is a fallback text version of the email.',
    html,
    attachments,
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

export const sendTemplatedBulkEmail = async ({
  recipients,
  subject,
  templateName,
  templateData,
}) => {
  const html = renderTemplate(templateName, templateData);

  await sendBulkEmail({
    recipients,
    subject,
    text: 'This is a fallback text version of the email.',
    html,
  });
};

/**
 * Sends a model evaluation failure email to a single recipient.
 * @param {Object} options - Email options.
 * @param {string} options.recipientName - Name of the recipient.
 * @param {string} options.recipientEmail - Email address of the recipient.
 * @param {string} options.agentName - Name of the agent.
 * @param {string} options.nodeName - Name of the node.
 * @param {string} options.inputPayload - Input payload for the model.
 * @param {string} options.outputPayload - Output payload from the model.
 * @param {string} options.reviewerSummary - Summary provided by the automatic evaluator.
 * @param {number} options.agentId - ID of the agent.
 * @param {number} options.agentLogId - ID of the agent log.
 * @returns {Promise<void>}
 */
export const sendModelReviewFailureEmail = async ({
  recipientName,
  recipientEmail,
  agentName,
  nodeName,
  inputPayload,
  outputPayload,
  reviewerSummary,
  agentId,
  modelLog,
  Email,
  User,
  notificationSource,
  sourceId,
}) => {
  const url = process.env.DASHBOARD_URL
    ? process.env.DASHBOARD_URL
    : 'http://localhost:3000';
  const subject = '🚨 Handit Alert: Automatic Evaluation Issue Detected';
  const agentLogId = modelLog.agentLogId || modelLog.dataValues?.agentLogId;
  const tracingUrl = `${url}/ag-tracing?agentId=${agentId}&entryLog=${agentLogId}`;

  // Get the modelId from the agentLog to create the optimize URL
  let modelId = null;
  let modelLogId = null;
  if (modelLog) {
    modelId = modelLog.modelId || modelLog.dataValues?.modelId;
    modelLogId = modelLog.id || modelLog.dataValues?.id;
  }

  const optimizeUrl =
    modelId && modelLogId
      ? `${url}/prompt-versions?agentId=${agentId}&modelId=${modelId}&autoOptimize=true&modelLogId=${modelLogId}`
      : null;

  const templateData = {
    recipient_name: recipientName,
    agent_name: agentName,
    node_name: nodeName,
    timestamp: new Date().toLocaleString(),
    input_payload: inputPayload,
    output_payload: outputPayload,
    reviewer_summary: reviewerSummary,
    tracing_url: tracingUrl,
    optimize_url: optimizeUrl,
    agent_id: agentId,
    model_id: modelId,
    model_log_id: modelLogId,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'modelReviewFailureTemplate',
    templateData,
    Email,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo-image',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-handit.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-image',
      },
    ],
    User,
    notificationSource,
    sourceId,
  });
};

/**
 * Sends model evaluation failure emails to all users of a company.
 * @param {Object} options - Email options.
 * @param {number} options.companyId - ID of the company.
 * @param {string} options.agentName - Name of the agent.
 * @param {string} options.nodeName - Name of the node.
 * @param {string} options.inputPayload - Input payload for the model.
 * @param {string} options.outputPayload - Output payload from the model.
 * @param {string} options.reviewerSummary - Summary provided by the automatic evaluator.
 * @param {number} options.agentId - ID of the agent.
 * @param {number} options.agentLogId - ID of the agent log.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @param {number} [options.sourceId] - ID of the source.
 * @returns {Promise<void>}
 */
export const sendModelReviewFailureEmailsToCompany = async ({
  companyId,
  agentName,
  nodeName,
  inputPayload,
  outputPayload,
  reviewerSummary,
  agentId,
  modelLog,
  Email,
  User,
  notificationSource,
  sourceId,
}) => {
  // Get all users from the company
  const users = await User.findAll({
    where: {
      companyId: companyId,
    },
  });

  // Send emails to each user
  for (const user of users) {
    await sendModelReviewFailureEmail({
      recipientName: `${user.firstName} ${user.lastName}`,
      recipientEmail: user.email,
      agentName,
      nodeName,
      inputPayload,
      outputPayload,
      reviewerSummary,
      agentId,
      modelLog,
      Email,
      User,
      notificationSource,
      sourceId,
    });
  }
};

/**
 * Sends a model failure notification email when a model log is updated and marked as failed.
 * @param {Object} modelLog - The model log that was updated.
 * @returns {Promise<void>}
 */
export const sendModelFailureNotification = async (
  modelLog,
  Model,
  AgentLog,
  Agent,
  AgentNode,
  Company,
  Email,
  User
) => {
  try {
    // Get the model
    const model = await Model.findByPk(
      modelLog.modelId ? modelLog.modelId : modelLog.dataValues?.modelId
    );
    if (!model) {
      console.error(`Model not found for modelLog ID: ${modelLog.id}`);
      return;
    }

    // Get the agent log
    const agentLog = await AgentLog.findByPk(
      modelLog.agentLogId
        ? modelLog.agentLogId
        : modelLog.dataValues?.agentLogId
    );
    if (!agentLog) {
      console.error(`Agent log not found for modelLog ID: ${modelLog.id}`);
      return;
    }

    // Get the agent
    const agent = await Agent.findByPk(
      agentLog.agentId ? agentLog.agentId : agentLog.dataValues?.agentId
    );
    if (!agent) {
      console.error(`Agent not found for agentLog ID: ${agentLog.id}`);
      return;
    }

    // Get the agent node
    const agentNode = await AgentNode.findOne({
      where: {
        agentId: agent.id ? agent.id : agent.dataValues?.id,
        modelId: model.id ? model.id : model.dataValues?.id,
      },
    });
    if (!agentNode) {
      console.error(
        `Agent node not found for agent ID: ${agent.id} and model ID: ${model.id}`
      );
      return;
    }

    // Get the company
    const company = await Company.findByPk(
      agent.companyId ? agent.companyId : agent.dataValues?.companyId
    );
    if (!company) {
      console.error(`Company not found for agent ID: ${agent.id}`);
      return;
    }

    // Prepare the reviewer summary

    let reviewerSummary = [];

    const evaluations = modelLog.actual?.evaluations;
    if (evaluations && evaluations.length > 0) {
      for (const evaluation of evaluations) {
        if (evaluation.evaluator && !evaluation.isInformative) {
          reviewerSummary.push(
            ' • ' + evaluation.evaluator + ': ' + evaluation.analysis
          );
        }
      }
    }

    // Send the email to all users of the company
    await sendModelReviewFailureEmailsToCompany({
      companyId: company.id,
      agentName: agent.name,
      nodeName: agentNode.name,
      inputPayload: JSON.stringify(modelLog.input),
      outputPayload: JSON.stringify(modelLog.output),
      reviewerSummary,
      agentId: agent.id,
      modelLog: modelLog,
      Email,
      User,
      notificationSource: 'model_log',
      sourceId: modelLog.id,
    });

    console.log(
      `Model failure notification sent for modelLog ID: ${modelLog.id}`
    );
  } catch (error) {
    console.error(
      `Error sending model failure notification for modelLog ID: ${modelLog.id}:`,
      error
    );
  }
};

/**
 * Sends a tool error notification email when an agent node log has an error.
 * @param {Object} agentNodeLog - The agent node log that contains the error.
 * @returns {Promise<void>}
 */
export const sendToolErrorNotification = async (
  agentNodeLog,
  Agent,
  AgentNode,
  Company,
  Email,
  User
) => {
  try {
    // Get the agent and agent node
    const agent = await Agent.findByPk(agentNodeLog.agentId);
    const agentNode = await AgentNode.findByPk(agentNodeLog.agentNodeId);
    const company = await Company.findByPk(agent.companyId);

    if (!agent || !agentNode || !company) {
      console.error(
        'Could not find agent, agent node, or company for tool error notification'
      );
      return;
    }

    // Get all users in the company
    const users = await User.findAll({
      where: { companyId: company.id },
    });

    // Construct the tracing URL
    const tracingUrl = `${process.env.DASHBOARD_URL}/agents/${agent.id}/logs/${agentNodeLog.parentLogId}`;

    // Extract error details from output.error and output.stack
    const errorMessage = agentNodeLog.output?.error || 'Unknown error';
    const errorStack = agentNodeLog.output?.stack;

    // Send email to each user
    for (const user of users) {
      await sendTemplatedEmail({
        to: user.email,
        subject: `[Handit.AI] Tool Error Alert - ${agent.name}`,
        templateName: 'toolErrorTemplate',
        templateData: {
          recipientName: user.name,
          agent_name: agent.name,
          node_name: agentNode.name,
          timestamp: new Date(agentNodeLog.createdAt).toLocaleString(),
          operation_type: agentNodeLog.operationType || 'tool_operation',
          error_message: errorMessage,
          error_stack: errorStack,
          tracing_url: tracingUrl,
          year: new Date().getFullYear(),
        },
        Email,
        User,
        notificationSource: 'agent_node',
        sourceId: agentNodeLog.id,
      });
    }
  } catch (error) {
    console.error('Error sending tool error notification:', error);
  }
};

export const sendWeeklyPerformanceEmail = async ({
  companyId,
  startDate,
  endDate,
  header,
  agents,
  Email,
  User,
  clientName,
  tracingUrl,
  notificationSource = 'weekly_performance',
  sourceId = null,
}) => {
  try {
    // Get company users who should receive the email
    const users = await User.findAll({
      where: {
        companyId: companyId,
      },
    });

    if (users.length === 0) {
      console.log(
        `No users found with active messages for company ${companyId} to receive weekly performance email`
      );
      return;
    }

    // Format dates
    const formattedStartDate = new Date(startDate).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
    const formattedEndDate = new Date(endDate).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });

    // Prepare template data
    const templateData = {
      client_name: clientName || 'Valued Client',
      agents: agents,
      tracing_url: tracingUrl || `https://dashboard.handit.ai/ag-monitoring`,
      year: new Date().getFullYear(),
      header,
    };

    // Send email to each user
    await sendTemplatedEmail({
      to: users.map((user) => user.email),
      subject: `Handit.AI Weekly Performance Report (${formattedStartDate} - ${formattedEndDate})`,
      templateName: 'weeklyPerformanceTemplate',
      templateData,
      attachments: [
        {
          content: fs
            .readFileSync(
              path.join(__dirname, 'src/services/templates/logo.png')
            )
            .toString('base64'),
          filename: 'logo.png',
          type: 'image/png',
          disposition: 'inline',
          content_id: 'logo-image',
        },
        {
          content: fs
            .readFileSync(
              path.join(__dirname, 'src/services/templates/bg-real.png')
            )
            .toString('base64'),
          filename: 'bg-handit.png',
          type: 'image/png',
          disposition: 'inline',
          content_id: 'bg-image',
        },
      ],
      Email,
      User,
      notificationSource,
      sourceId,
    });

    console.log(
      `Weekly performance email sent to ${users.length} users for company ${companyId}`
    );
  } catch (error) {
    console.error(
      `Error sending weekly performance email for company ${companyId}:`,
      error
    );
  }
};

export const sendAutonomWaitlistEmail = async ({
  recipientEmail,
  firstName,
  Email,
  User,
  notificationSource = 'autonom_waitlist',
  sourceId = null,
}) => {
  const subject = '🚀 Welcome to the Autonom Waitlist!';

  const templateData = {
    first_name: firstName,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'autonomWaitlistTemplate',
    templateData,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo-image',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-handit.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-image',
      },
    ],
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

export const sendWelcomeNewUserEmail = async ({
  recipientEmail,
  firstName,
  password,
  Email,
  User,
  notificationSource = 'welcome_new_user',
  sourceId = null,
}) => {
  const subject = '🎉 Welcome to Handit.ai!';

  const templateData = {
    first_name: firstName,
    email: recipientEmail,
    password: password,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'welcomeNewUserTemplate',
    templateData,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo-image',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-handit.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-image',
      },
    ],
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

export const sendWelcomeHanditEmail = async ({
  recipientEmail,
  firstName,
  Email,
  User,
  notificationSource = 'welcome_handit',
  sourceId = null,
}) => {
  const subject =
    'Welcome to handit.ai - The Open-Source Engine that Auto-Fixes Your AI';

  const templateData = {
    first_name: firstName,
    email: recipientEmail,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'welcomeHanditTemplate',
    templateData,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo-image',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-handit.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-image',
      },
    ],
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

/**
 * Sends a re-engagement email to inactive users who haven't set up AI observability.
 * @param {Object} options - Email options.
 * @param {string} options.recipientEmail - Email address of the recipient.
 * @param {string} options.firstName - First name of the recipient.
 * @param {number} options.daysSinceRegistration - Number of days since user registration.
 * @param {string} [options.quickstartUrl] - URL to the quickstart guide.
 * @param {Object} options.Email - Email model for database operations.
 * @param {Object} options.User - User model for database operations.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @param {number} [options.sourceId] - ID of the source.
 * @returns {Promise<void>}
 */
export const sendReEngagementEmail = async ({
  recipientEmail,
  firstName,
  daysSinceRegistration,
  quickstartUrl = 'https://docs.handit.ai/quickstart',
  Email,
  User,
  notificationSource = 're_engagement',
  sourceId = null,
}) => {
  const subject = 'Complete Your Handit.AI Setup in 5 Minutes ⏱️';

  const templateData = {
    firstName: firstName,
    daysSinceRegistration: daysSinceRegistration,
    quickstartUrl: quickstartUrl,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'reEngagement/inactiveUserTemplate',
    templateData,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-real.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-real',
      },
    ],
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

/**
 * Sends bulk re-engagement emails to multiple inactive users.
 * @param {Object} options - Bulk email options.
 * @param {Array} options.inactiveUsers - Array of inactive user objects with email, firstName, and daysSinceRegistration.
 * @param {string} [options.quickstartUrl] - URL to the quickstart guide.
 * @param {Object} options.Email - Email model for database operations.
 * @param {Object} options.User - User model for database operations.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @returns {Promise<void>}
 */
export const sendBulkReEngagementEmails = async ({
  inactiveUsers,
  quickstartUrl = 'https://dashboard.handit.ai',
  Email,
  User,
  notificationSource = 're_engagement_bulk',
}) => {
  console.log(
    `Starting bulk re-engagement email campaign for ${inactiveUsers.length} users`
  );

  const results = {
    sent: 0,
    failed: 0,
    errors: [],
  };

  for (const user of inactiveUsers) {
    try {
      await sendReEngagementEmail({
        recipientEmail: user.email,
        firstName: user.firstName,
        daysSinceRegistration: user.daysSinceRegistration,
        quickstartUrl,
        Email,
        User,
        notificationSource,
        sourceId: user.id,
      });

      results.sent++;
      console.log(`✅ Re-engagement email sent to ${user.email}`);

      // Small delay between emails to avoid rate limiting
      await new Promise((resolve) => setTimeout(resolve, 100));
    } catch (error) {
      results.failed++;
      results.errors.push({
        email: user.email,
        error: error.message,
      });
      console.error(
        `❌ Failed to send re-engagement email to ${user.email}:`,
        error.message
      );
    }
  }

  console.log(
    `🎯 Bulk re-engagement campaign completed: ${results.sent} sent, ${results.failed} failed`
  );
  return results;
};

/**
 * Sends an email to users with agents that don't have evaluators connected.
 * @param {Object} options - Email options.
 * @param {string} options.recipientEmail - Email address of the recipient.
 * @param {string} options.firstName - First name of the recipient.
 * @param {number} options.daysSinceAgentCreation - Number of days since agent creation.
 * @param {string} [options.evaluationHubUrl] - URL to the evaluation hub.
 * @param {Object} options.Email - Email model for database operations.
 * @param {Object} options.User - User model for database operations.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @param {number} [options.sourceId] - ID of the source.
 * @returns {Promise<void>}
 */
export const sendAgentsWithoutEvaluatorsEmail = async ({
  recipientEmail,
  firstName,
  daysSinceAgentCreation,
  evaluationHubUrl = 'https://dashboard.handit.ai/evaluation-hub',
  Email,
  User,
  notificationSource = 'agents_without_evaluators',
  sourceId = null,
}) => {
  const subject = 'Connect Evaluators to Your AI - Complete Your Setup 🎯';

  const templateData = {
    firstName: firstName,
    daysSinceAgentCreation: daysSinceAgentCreation,
    evaluationHubUrl: evaluationHubUrl,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'reEngagement/agentsWithoutEvaluatorsTemplate',
    templateData,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-real.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-real',
      },
    ],
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

/**
 * Sends bulk emails to users with agents that don't have evaluators connected.
 * @param {Object} options - Bulk email options.
 * @param {Array} options.agentsWithoutEvaluators - Array of user objects with email, firstName, and daysSinceAgentCreation.
 * @param {string} [options.evaluationHubUrl] - URL to the evaluation hub.
 * @param {Object} options.Email - Email model for database operations.
 * @param {Object} options.User - User model for database operations.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @returns {Promise<void>}
 */
export const sendBulkAgentsWithoutEvaluatorsEmails = async ({
  agentsWithoutEvaluators,
  evaluationHubUrl = 'https://dashboard.handit.ai/evaluation-hub',
  Email,
  User,
  notificationSource = 'agents_without_evaluators_bulk',
}) => {
  console.log(
    `Starting bulk agents without evaluators email campaign for ${agentsWithoutEvaluators.length} users`
  );

  const results = {
    sent: 0,
    failed: 0,
    errors: [],
  };

  for (const user of agentsWithoutEvaluators) {
    try {
      await sendAgentsWithoutEvaluatorsEmail({
        recipientEmail: user.email,
        firstName: user.firstName,
        daysSinceAgentCreation: user.daysSinceAgentCreation,
        evaluationHubUrl,
        Email,
        User,
        notificationSource,
        sourceId: user.id,
      });

      results.sent++;
      console.log(`✅ Agents without evaluators email sent to ${user.email}`);

      // Small delay between emails to avoid rate limiting
      await new Promise((resolve) => setTimeout(resolve, 100));
    } catch (error) {
      results.failed++;
      results.errors.push({
        email: user.email,
        error: error.message,
      });
      console.error(
        `❌ Failed to send agents without evaluators email to ${user.email}:`,
        error.message
      );
    }
  }

  console.log(
    `🎯 Bulk agents without evaluators campaign completed: ${results.sent} sent, ${results.failed} failed`
  );
  return results;
};

/**
 * Sends an email when Handit automatically creates an improved prompt version.
 * @param {Object} options - Email options.
 * @param {string} options.recipientEmail - Email address of the recipient.
 * @param {string} options.firstName - First name of the recipient.
 * @param {string} options.agentName - Name of the agent.
 * @param {string} options.modelName - Name of the model.
 * @param {string} options.promptVersion - Version of the prompt.
 * @param {number} options.agentId - ID of the agent.
 * @param {number} options.modelId - ID of the model.
 * @param {string} [options.promptVersionsUrl] - URL to the prompt versions page.
 * @param {Object} options.Email - Email model for database operations.
 * @param {Object} options.User - User model for database operations.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @param {number} [options.sourceId] - ID of the source.
 * @returns {Promise<void>}
 */
export const sendPromptVersionCreatedEmail = async ({
  recipientEmail,
  firstName,
  agentName,
  modelName,
  promptVersion,
  agentId,
  modelId,
  promptVersionsUrl = 'http://localhost:3000/prompt-versions',
  Email,
  User,
  notificationSource = 'prompt_version_created',
  sourceId = null,
}) => {
  const subject = 'Handit Found an Improved Version of Your Prompt 🚀';

  const templateData = {
    firstName: firstName,
    agentName: agentName,
    modelName: modelName,
    promptVersion: promptVersion,
    agentId: agentId,
    modelId: modelId,
    promptVersionsUrl: `${promptVersionsUrl}?agentId=${agentId}&modelId=${modelId}&promptVersion=${promptVersion}&autoDeploy=true`,
    year: new Date().getFullYear(),
  };

  await sendTemplatedEmail({
    to: recipientEmail,
    subject,
    templateName: 'reEngagement/promptVersionCreatedTemplate',
    templateData,
    attachments: [
      {
        content: fs
          .readFileSync(path.join(__dirname, 'src/services/templates/logo.png'))
          .toString('base64'),
        filename: 'logo.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'logo',
      },
      {
        content: fs
          .readFileSync(
            path.join(__dirname, 'src/services/templates/bg-real.png')
          )
          .toString('base64'),
        filename: 'bg-real.png',
        type: 'image/png',
        disposition: 'inline',
        content_id: 'bg-real',
      },
    ],
    Email,
    User,
    notificationSource,
    sourceId,
  });
};

/**
 * Sends bulk emails when Handit automatically creates improved prompt versions.
 * @param {Object} options - Bulk email options.
 * @param {Array} options.promptVersionNotifications - Array of notification objects with email, firstName, agentName, modelName, promptVersion, agentId, modelId.
 * @param {string} [options.promptVersionsUrl] - URL to the prompt versions page.
 * @param {Object} options.Email - Email model for database operations.
 * @param {Object} options.User - User model for database operations.
 * @param {string} [options.notificationSource] - Source of the notification.
 * @returns {Promise<void>}
 */
export const sendBulkPromptVersionCreatedEmails = async ({
  promptVersionNotifications,
  promptVersionsUrl = 'https://dashboard.handit.ai/prompt-versions',
  Email,
  User,
  notificationSource = 'prompt_version_created_bulk',
}) => {
  console.log(
    `Starting bulk prompt version created email campaign for ${promptVersionNotifications.length} users`
  );

  const results = {
    sent: 0,
    failed: 0,
    errors: [],
  };

  for (const notification of promptVersionNotifications) {
    try {
      await sendPromptVersionCreatedEmail({
        recipientEmail: notification.email,
        firstName: notification.firstName,
        agentName: notification.agentName,
        modelName: notification.modelName,
        promptVersion: notification.promptVersion,
        agentId: notification.agentId,
        modelId: notification.modelId,
        promptVersionsUrl,
        Email,
        User,
        notificationSource,
        sourceId: notification.id,
      });

      results.sent++;
      console.log(
        `✅ Prompt version created email sent to ${notification.email}`
      );

      // Small delay between emails to avoid rate limiting
      await new Promise((resolve) => setTimeout(resolve, 100));
    } catch (error) {
      results.failed++;
      results.errors.push({
        email: notification.email,
        error: error.message,
      });
      console.error(
        `❌ Failed to send prompt version created email to ${notification.email}:`,
        error.message
      );
    }
  }

  console.log(
    `🎯 Bulk prompt version created campaign completed: ${results.sent} sent, ${results.failed} failed`
  );
  return results;
};
