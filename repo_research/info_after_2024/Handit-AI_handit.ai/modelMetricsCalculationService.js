import { parseInput } from "./parseInput.js";
import { Op } from 'sequelize';

export const getMetricOfModelMonitoring = async (modelId, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);
  const modelMetrics = await sequelize.models.ModelMetric.findAll({ where: { modelId } });
  const modelMetricIds = modelMetrics.map((modelMetric) => modelMetric.id);
  const modelMetricLogs = await sequelize.models.ModelMetricLog.findAll({
    where: { modelMetricId: modelMetricIds },
    order: [['created_at', 'DESC']],
  });

  const maxIds = modelMetricLogs.reduce((acc, modelMetricLog) => {
    if (!acc[modelMetricLog.modelMetricId]) {
      acc[modelMetricLog.modelMetricId] = modelMetricLog.id;
    }
    return acc;
  }, {});

  let modelMetricLogsByModelMetricId = modelMetricLogs.reduce(
    (acc, modelMetricLog) => {
      if (modelMetricLog.id === maxIds[modelMetricLog.modelMetricId]) {
        acc[modelMetricLog.modelMetricId] = modelMetricLog;
      }
      return acc;
    },
    {}
  );
  const transformedModelMetricLogsByModelMetricId = {};

  for (let i = 0; i < Object.keys(modelMetricLogsByModelMetricId).length; i++) {
    const key = Object.keys(modelMetricLogsByModelMetricId)[i];
    const metric = modelMetricLogsByModelMetricId[key];
    if (metric.label === 'health_check') {
      if (metric.value === 0) {
        metric.value = 'Error';
      } else {
        if (await failedCheckInLast24H(modelId, sequelize)) {
          metric.value = 'Warning';
        } else {
          metric.value = 'Success';
        }
      }
    }
    transformedModelMetricLogsByModelMetricId[key] = metric;
  }

  const alertsCount = await model.getLastAlertsCount();
  const errorsCount = await model.getLastErrorsCount();
  const lastAlertsByHour = await model.getLastAlertsHourByHour();

  return {
    ...model.dataValues,
    lastAlerts: alertsCount,
    lastErrors: errorsCount,
    lastAlertsByHour,
    modelMetrics: modelMetrics.map((modelMetric) => {
      const modelMetricLog =
        transformedModelMetricLogsByModelMetricId[modelMetric.id];
      return {
        ...modelMetric.toJSON(),
        modelMetricLog: modelMetricLog ? modelMetricLog.toJSON() : null,
        lastModelMetricLogTime: modelMetricLog
          ? modelMetricLog.createdAt
          : null,
      };
    }),
  };
};


export const failedCheckInLast24H = async (modelId, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);
  const modelMetrics = await sequelize.models.ModelMetric.findAll({ where: { modelId } });
  if (!model) {
    return null;
  }
  const lastHealthCheck = await sequelize.models.ModelMetricLog.findAll({
    where: {
      modelMetricId: modelMetrics.map((modelMetric) => modelMetric.id),
      label: 'health_check',
      createdAt: {
        [Op.gt]: new Date(new Date() - 24 * 60 * 60 * 1000),
      },
    },
  });
  return lastHealthCheck.some((healthCheck) => healthCheck.value === 0);
};

export const getModelCorrectEntriesByDay = async (modelId, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);

  const correctEntriesByDay = await model.getCorrectEntriesFromDateDayByDay(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
  );

  const incorrectEntriesByDay = await model.getIncorrectEntriesFromDateDayByDay(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
  );


  const correctNormalizedEntriesByDay = {};

  Object.keys(correctEntriesByDay).map((key, index) => {
    if (correctEntriesByDay[key] + incorrectEntriesByDay[key] === 0) {
      correctNormalizedEntriesByDay[key] = 0;
    }
    correctNormalizedEntriesByDay[key] =
      ((correctEntriesByDay[key] * 1.0));
  });

  const incorrectNormalizedEntriesByDay = {};

  Object.keys(incorrectEntriesByDay).map((key, index) => {
    if (correctEntriesByDay[key] + incorrectEntriesByDay[key] === 0) {
      incorrectNormalizedEntriesByDay[key] = 0;
    }
    incorrectNormalizedEntriesByDay[key] =
      ((incorrectEntriesByDay[key]));
  });

  return {
    correctEntriesByDay: correctEntriesByDay,
    incorrectEntriesByDay: incorrectEntriesByDay,
  };
};



export const getModelNumberOfAlertsByType = async (modelId, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);

  const numberOfAlertsByTypeThisMonth =
    await model.getNumberOfAlertsByTypeByMonth();
  const numberOfAlertsByTypeLastMonth =
    await model.getNumberOfAlertsByTypeByMonth(
      new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
    );
  const differenceAlertsByType = Object.keys(
    numberOfAlertsByTypeThisMonth
  ).reduce((acc, key) => {
    acc[key] =
      numberOfAlertsByTypeThisMonth[key] - numberOfAlertsByTypeLastMonth[key];
    return acc;
  }, {});

  return {
    numberOfAlertsByTypeThisMonth,
    numberOfAlertsByTypeLastMonth,
    differenceAlertsByType,
  };
};

export const getModelLastModelMetrics = async (modelId, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);
  const lastModelMetrics = await model.getLastModelMetrics();
  return { lastModelMetrics };
};

export const generateDemoModelMetricsFullDate = async (modelMetrics, optimized) => {
  const lastMetricsLogs = {};
  const avgModelMetricsCurrentMonth = {};
  
  // Model phases configuration (total improvement: 34.2%)
  const phaseValues = {
    base: 40,
    initial: 45,      // Base starting point
    improved: 65,     // Middle phase
    optimized: 79.2   // Latest phase
  };
  
  // Improvements within phases
  const improvements = {
    base: 0,
    initial: 2,
    improved: 3,
    optimized: 3.5
  };
  
  // Spike configuration
  const spikeConfig = {
    chance: 0.2,
    positive: { 
      min: 2.5, 
      max: 5 
    },
    negative: { 
      min: 2, 
      max: 4 
    }
  };
  
  // iterate over the last 30 days (from oldest to newest)
  for (let i = 29; i >= 0; i--) {
    const date = new Date(new Date() - i * 24 * 60 * 60 * 1000);
    date.setHours(0);
    date.setMinutes(0);
    date.setSeconds(0);
    
    lastMetricsLogs[date.toUTCString()] = {};
    
    // Phase determination
    const optimizedPhase = i >= 20 ? 'initial' : (i >= 10 ? 'improved' : 'optimized');
    const basePhase = i >= 20 ? 'base' : (i >= 10 ? 'initial' : 'improved'); // One phase behind
    
    // Progress within current phase (0-1)
    const phaseProgress = optimizedPhase === 'initial' ? (29 - i) / 10 :
                         optimizedPhase === 'improved' ? (19 - i) / 10 :
                         (9 - i) / 10;
    
    const isTransitionDay = i === 20 || i === 10;
    const isDayAfterTransition = i === 19 || i === 9;
    
    for (const modelMetric of modelMetrics) {
      let metricValue;
      
      if (!optimized) {
        // Base model (one phase behind optimized)
        metricValue = phaseValues[basePhase] + (improvements[basePhase] * phaseProgress);
        
        // Add base variation
        const normalVariation = (Math.random() * 3 - 1.5) * 1.5;
        metricValue += normalVariation;
        
        // Add spikes
        if (Math.random() < spikeConfig.chance && !isTransitionDay) {
          const isPositiveSpike = Math.random() > 0.45;
          let spikeAmount = 0;
          
          if (isPositiveSpike) {
            spikeAmount = Math.random() * 
              (spikeConfig.positive.max - spikeConfig.positive.min) + 
              spikeConfig.positive.min;
            metricValue += spikeAmount;
          } else {
            spikeAmount = Math.random() * 
              (spikeConfig.negative.max - spikeConfig.negative.min) + 
              spikeConfig.negative.min;
            metricValue -= spikeAmount;
            
            // Add recovery chance after dips
            if (Math.random() > 0.7) {
              const recoveryFactor = Math.random() * 0.8 + 0.2;
              metricValue += spikeAmount * recoveryFactor;
            }
          }
        }
        
        // Handle base model transitions (smaller than optimized)
        if (isTransitionDay) {
          metricValue = phaseValues[basePhase] - 1;
        } else if (isDayAfterTransition) {
          metricValue = phaseValues[basePhase] + 0.5;
        }
        
      } else {
        // Optimized model
        metricValue = phaseValues[optimizedPhase] + (improvements[optimizedPhase] * phaseProgress);
        
        // Add variation
        const normalVariation = (Math.random() * 3 - 1.5) * 1.5;
        metricValue += normalVariation;
        
        // Add spikes
        if (Math.random() < spikeConfig.chance && !isTransitionDay && !isDayAfterTransition) {
          const isPositiveSpike = Math.random() > 0.45;
          if (isPositiveSpike) {
            const spikeAmount = Math.random() * 
              (spikeConfig.positive.max - spikeConfig.positive.min) + 
              spikeConfig.positive.min;
            metricValue += spikeAmount;
          } else {
            const spikeAmount = Math.random() * 
              (spikeConfig.negative.max - spikeConfig.negative.min) + 
              spikeConfig.negative.min;
            metricValue -= spikeAmount;
          }
        }
        
        // Handle optimized model transitions
        if (isTransitionDay) {
          metricValue = phaseValues[optimizedPhase] - 1.5;
        } else if (isDayAfterTransition) {
          metricValue = phaseValues[optimizedPhase] + 0.8;
        }
      }
      
      // Ensure values stay within reasonable bounds
      const currentPhase = optimized ? optimizedPhase : basePhase;
      const minValue = phaseValues[currentPhase] - 5;
      const maxValue = phaseValues[currentPhase] + improvements[currentPhase] + 5;
      
      metricValue = Math.min(Math.max(metricValue, minValue), maxValue);
      lastMetricsLogs[date.toUTCString()][modelMetric.dataValues.id] = metricValue;
    }
  }

  // Calculate current month averages (based on last 7 days for more stability)
  for (const modelMetric of modelMetrics) {
    const lastSevenDays = Object.values(lastMetricsLogs).slice(-7);
    const avgLastWeek = lastSevenDays.reduce((sum, day) => 
      sum + day[modelMetric.dataValues.id], 0) / 7;
    
    avgModelMetricsCurrentMonth[modelMetric.dataValues.id] = 
      Math.min(avgLastWeek / 100, 0.95);
  }

  // divide the values by 100
  Object.keys(lastMetricsLogs).forEach((key) => {
    Object.keys(lastMetricsLogs[key]).forEach((metricId) => {
      lastMetricsLogs[key][metricId] = lastMetricsLogs[key][metricId] / 100.0;
    });
  });

  return {
    lastMetricLogs: lastMetricsLogs,
    avgModelMetricsCurrentMonth,
    modelMetrics,
  };
};



export const getModelMetricsFullDate = async (modelId, optimized, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);
  const modelGroup = await model.getModelGroup();
  const company = await modelGroup.getCompany();
  const modelMetrics = await sequelize.models.ModelMetric.findAll({ where: { modelId } });
  if (company.testMode) {
    return await generateDemoModelMetricsFullDate(modelMetrics, optimized);
  }

  const modelMetricLogs = await sequelize.models.ModelMetricLog.findAll({
    where: {
      modelMetricId: modelMetrics.map((modelMetric) => modelMetric.id),
      createdAt: {
        [Op.gt]: new Date(new Date() - 30 * 24 * 60 * 60 * 1000),
      },
    },
  });
  const lastMetricLogs = await model.getLastMetricLogsFromDateDayByDay(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000),
    modelMetricLogs
  );
  const avgModelMetricsCurrentMonth = await model.getAvgModelMetricsLast30Days(
    new Date(),
    modelMetricLogs
  );
  return {
    modelMetrics: modelMetrics,
    lastMetricLogs,
    avgModelMetricsCurrentMonth,
  };
};

export const getModelMetricsOfModelById = async (modelId, sequelize) => {
  const model = await sequelize.models.Model.findByPk(modelId);
  const modelMetrics = await sequelize.models.ModelMetric.findAll({ where: { modelId } });
  // get last model metric logs of each model metric
  const modelMetricIds = modelMetrics.map((modelMetric) => modelMetric.id);
  const modelMetricLogs = await sequelize.models.ModelMetricLog.findAll({
    where: { modelMetricId: modelMetricIds },
    order: [['created_at', 'DESC']],
  });

  const maxIds = modelMetricLogs.reduce((acc, modelMetricLog) => {
    if (!acc[modelMetricLog.modelMetricId]) {
      acc[modelMetricLog.modelMetricId] = modelMetricLog.id;
    }
    return acc;
  }, {});

  let modelMetricLogsByModelMetricId = modelMetricLogs.reduce(
    (acc, modelMetricLog) => {
      if (modelMetricLog.id === maxIds[modelMetricLog.modelMetricId]) {
        acc[modelMetricLog.modelMetricId] = modelMetricLog;
      }
      return acc;
    },
    {}
  );
  const transformedModelMetricLogsByModelMetricId = {};

  for (let i = 0; i < Object.keys(modelMetricLogsByModelMetricId).length; i++) {
    const key = Object.keys(modelMetricLogsByModelMetricId)[i];
    const metric = modelMetricLogsByModelMetricId[key];
    if (metric.label === 'health_check') {
      if (metric.value === 0) {
        metric.value = 'Error';
      } else {
        if (await failedCheckInLast24H(modelId, sequelize)) {
          metric.value = 'Warning';
        } else {
          metric.value = 'Success';
        }
      }
    }
    transformedModelMetricLogsByModelMetricId[key] = metric;
  }

  const alertsCount = await model.getLastAlertsCount();
  const errorsCount = await model.getLastErrorsCount();
  const lastAlert = await model.getLastAlert();
  const lastAlertsByHour = await model.getLastAlertsHourByHour();
  const lastAlerts30Days = await model.getLastAlerts30DaysByDay();
  const lastHealthErrorDays = await model.lastHealtchErrorDays();
  const lastHealthWarningDays = await model.lastHealtchWarningDays();
  const groupedAlerts = await model.groupedAlerts();
  const lastMetricLogs = await model.getLastMetricLogsFromDateDayByDay(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
  );
  const correctEntriesByDay = await model.getCorrectEntriesFromDateDayByDay(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
  );

  const incorrectEntriesByDay = await model.getIncorrectEntriesFromDateDayByDay(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
  );

  const correctNormalizedEntriesByDay = {};

  Object.keys(correctEntriesByDay).map((key, index) => {
    if (correctEntriesByDay[key] + incorrectEntriesByDay[key] === 0) {
      correctNormalizedEntriesByDay[key] = 0;
    }
    correctNormalizedEntriesByDay[key] =
      ((correctEntriesByDay[key] * 1.0) /
        (correctEntriesByDay[key] + incorrectEntriesByDay[key])) *
      100.0;
  });

  const incorrectNormalizedEntriesByDay = {};

  Object.keys(incorrectEntriesByDay).map((key, index) => {
    if (correctEntriesByDay[key] + incorrectEntriesByDay[key] === 0) {
      incorrectNormalizedEntriesByDay[key] = 0;
    }
    incorrectNormalizedEntriesByDay[key] =
      ((incorrectEntriesByDay[key] * 1.0) /
        (correctEntriesByDay[key] + incorrectEntriesByDay[key])) *
      100.0;
  });

  const numberOfAlertsByTypeThisMonth =
    await model.getNumberOfAlertsByTypeByMonth();
  const numberOfAlertsByTypeLastMonth =
    await model.getNumberOfAlertsByTypeByMonth(
      new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
    );
  const differenceAlertsByType = Object.keys(
    numberOfAlertsByTypeThisMonth
  ).reduce((acc, key) => {
    acc[key] =
      numberOfAlertsByTypeThisMonth[key] - numberOfAlertsByTypeLastMonth[key];
    return acc;
  }, {});
  const lastModelMetrics = await model.getLastModelMetrics();
  const avgModelMetricsCurrentMonth =
    await model.getAvgModelMetricsLast30Days();
  const avgModelMetricsLastMonth = await model.getAvgModelMetricsLast30Days(
    new Date(new Date() - 30 * 24 * 60 * 60 * 1000)
  );
  let prompt = '';
  const modelPrompt = await model.prompt();
  if (modelPrompt) {
    prompt = modelPrompt;
  } else {
    const lastModelLog = await model.getLastModelLog();

    if (lastModelLog) {
      try {
        prompt = parseInput(lastModelLog.dataValues.input, 0, -1);
      } catch (e) {
        prompt = '';
      }
    }
  }

  const differenceModelMetrics = Object.keys(lastModelMetrics).reduce(
    (acc, key) => {
      acc[key] =
        (lastModelMetrics[key].value || 0) -
        (avgModelMetricsLastMonth[lastModelMetrics[key].value] || 0);
      return acc;
    },
    {}
  );
  return {
    ...model.dataValues,
    lastModelMetrics,
    avgModelMetricsCurrentMonth,
    avgModelMetricsLastMonth,
    differenceModelMetrics,
    lastAlerts: alertsCount,
    lastHealthErrorDays,
    groupedAlerts,
    lastHealthWarningDays,
    lastAlertCreatedAt: lastAlert ? lastAlert.createdAt : null,
    lastErrors: errorsCount,
    lastMetricLogs,
    lastAlertsByHour,
    lastAlerts30Days,
    correctEntriesByDay: correctNormalizedEntriesByDay,
    incorrectEntriesByDay: incorrectNormalizedEntriesByDay,
    numberOfAlertsByTypeThisMonth,
    prompt,
    differenceAlertsByType,
    modelMetrics: modelMetrics.map((modelMetric) => {
      const modelMetricLog =
        transformedModelMetricLogsByModelMetricId[modelMetric.id];
      return {
        ...modelMetric.toJSON(),
        modelMetricLog: modelMetricLog ? modelMetricLog.toJSON() : null,
        lastModelMetricLogTime: modelMetricLog
          ? modelMetricLog.createdAt
          : null,
      };
    }),
  };
};
