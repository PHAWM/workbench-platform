// utils/outcomeEvaluationHandlers.js
import { uploadAPI, evaluationAPI } from "../api/apiService";

/**
 * Maps meetMetric values to recommendation codes
 * Yes = 3, No = 1, Maybe = 2, NotEvaluated = 0
 */
export const getRecommendation = (meetMetric) => {
  switch (meetMetric) {
    case 'Yes': return 3;
    case 'Maybe': return 2;
    case 'No': return 1;
    case 'NotEvaluated': return 0;
    case null:
    case undefined: return 0;
    default: return 0;
  }
};

/**
 * Maps meet_requirement value back to meetMetric string
 */
export const mapMeetRequirementToMetric = (meetRequirement) => {
  if (meetRequirement === 'yes' || meetRequirement === 3) return 'Yes';
  if (meetRequirement === 'no' || meetRequirement === 1) return 'No';
  if (meetRequirement === 'maybe' || meetRequirement === 2) return 'Maybe';
  if (meetRequirement === 'not_evaluated' || meetRequirement === 0) return 'NotEvaluated';
  return null;
};

/**
 * Calculates summary statistics from evaluation results
 */
export const calculateEvaluationSummary = (results) => {
  const yesCount = results.filter(r => r.meetMetric === 'Yes').length;
  const noCount = results.filter(r => r.meetMetric === 'No').length;
  const maybeCount = results.filter(r => r.meetMetric === 'Maybe').length;
  const notEvaluatedCount = results.filter(r => !r.meetMetric || r.meetMetric === 'NotEvaluated').length;
  const totalCount = results.length;

  return {
    yes: yesCount,
    no: noCount,
    maybe: maybeCount,
    notEvaluated: notEvaluatedCount,
    total: totalCount,
    percentages: {
      yes: totalCount > 0 ? Math.round((yesCount / totalCount) * 100) : 0,
      no: totalCount > 0 ? Math.round((noCount / totalCount) * 100) : 0,
      maybe: totalCount > 0 ? Math.round((maybeCount / totalCount) * 100) : 0,
      notEvaluated: totalCount > 0 ? Math.round((notEvaluatedCount / totalCount) * 100) : 0
    }
  };
};

/**
 * Parses a CSV line handling quoted values
 */
export const parseCSVLine = (line) => {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
};

/**
 * Parses CSV text into headers and records
 */
export const parseCSVContent = (text) => {
  const lines = text.split(/\r?\n/).filter(line => line.trim() !== '');

  if (lines.length === 0) {
    throw new Error('CSV file is empty');
  }

  const headers = parseCSVLine(lines[0]);
  const records = lines.slice(1).map((line, i) => {
    const values = parseCSVLine(line);
    const record = { id: i + 1 };
    headers.forEach((header, idx) => {
      record[header] = values[idx] || '';
    });
    return record;
  });

  return { headers, records };
};

/**
 * Checks if a file is an audio file based on extension
 */
export const isAudioFile = (fileName) => {
  const fileExtension = fileName.split('.').pop().toLowerCase();
  return ['wav', 'mp3', 'ogg', 'webm', 'aac', 'm4a'].includes(fileExtension);
};

/**
 * Checks if a file is a CSV file based on extension
 */
export const isCsvFile = (fileName) => {
  const fileExtension = fileName.split('.').pop().toLowerCase();
  return fileExtension === 'csv';
};

/**
 * Extracts a string value from an input field that may be string or object
 */
export const extractInputValue = (input) => {
  if (typeof input === 'string') return input;
  if (typeof input === 'object' && input?.file_name) return input.file_name;
  return JSON.stringify(input);
};

/**
 * Extracts a string value from an output field that may be string or object
 */
export const extractOutputValue = (output) => {
  if (typeof output === 'string') return output;
  if (typeof output === 'object' && output?.classification) return output.classification;
  if (typeof output === 'object') return JSON.stringify(output);
  return String(output || '');
};

/**
 * Uploads a file to the server
 */
export const uploadFileToServer = async (auditId, fileObj, setFiles, setUploadedFile, toast) => {
  try {
    setFiles(prev =>
      prev.map(f => (f.id === fileObj.id ? { ...f, progress: 0 } : f))
    );

    // console.log('Uploading file:', fileObj.name);
    const response = await uploadAPI.uploadSingleDataset(auditId, fileObj.file);
    // console.log('Upload response:', response);

    const uploadedFileInfo = response.uploaded_files?.[0];
    const serverFilename = uploadedFileInfo?.filename || fileObj.name;
    const dataId = uploadedFileInfo?.data_id;

    setFiles(prev =>
      prev.map(f =>
        f.id === fileObj.id
          ? {
              ...f,
              progress: 100,
              url: URL.createObjectURL(fileObj.file),
              serverFilename: serverFilename,
              dataId: dataId
            }
          : f
      )
    );

    setUploadedFile({
      file: fileObj.file,
      serverFilename: serverFilename,
      originalFilename: fileObj.name,
      dataId: dataId
    });

    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
    return { success: true, serverFilename, dataId };
  } catch (err) {
    // console.log(err.response)
    const serverErrorMessage = err.response?.data?.detail || "An unexpected error occurred";
    toast.error(serverErrorMessage);
    setFiles(prev => prev.filter(f => f.id !== fileObj.id));
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
    return { success: false, error: err.message };
  }
};

/**
 * Deletes a file from the server
 */
export const deleteFile = async (auditId, fileName, setFiles, setUploadedFile) => {
  const confirmDelete = window.confirm("Are you sure you want to delete this file?");
  if (!confirmDelete) return { success: false, cancelled: true };

  try {
    const data = { filename: fileName };
    // console.log('Deleting file:', fileName);
    const response = await uploadAPI.deleteUploadedDataset(parseInt(auditId), data);
    // console.log('Delete response:', response);

    setFiles(prev => prev.filter(f => f.serverFilename !== fileName));
    setUploadedFile(prev => {
      if (prev?.serverFilename === fileName) return null;
      return prev;
    });

    // console.log('File deleted and list updated');
    return { success: true };
  } catch (error) {
    console.error('Error deleting file:', error);
    alert(`Failed to delete file: ${error.message || 'Unknown error'}`);
    return { success: false, error: error.message };
  }
};

/**
 * Downloads a file from the server
 */
export const downloadFile = async (auditId, fileObj) => {
  try {
    if (!fileObj.serverFilename) {
      alert('Cannot download: file not uploaded to server yet');
      return { success: false };
    }

    // console.log('Downloading file:', fileObj.serverFilename);
    const response = await uploadAPI.viewFile(auditId, fileObj.serverFilename);

    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileObj.name || fileObj.serverFilename;
    document.body.appendChild(a);
    a.click();

    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);

    // console.log('File downloaded successfully');
    return { success: true };
  } catch (err) {
    console.error('Download failed:', err);
    alert(`Failed to download file: ${err.message}`);
    return { success: false, error: err.message };
  }
};

/**
 * Views/previews a file (returns file data for modal display)
 */
export const viewFile = async (auditId, fileObj, toast) => {
  try {
    let text;
    let blob;

    const fileName = fileObj.name || fileObj.serverFilename || '';
    const audioFile = isAudioFile(fileName);
    const csvFile = isCsvFile(fileName);

    if (fileObj.isExisting && fileObj.serverFilename) {
      // console.log('Downloading file from server:', fileObj.serverFilename);
      const response = await uploadAPI.viewFile(auditId, fileObj.serverFilename);

      if (!response.ok) {
        throw new Error(`Failed to download file: ${response.statusText}`);
      }

      if (audioFile) {
        blob = await response.blob();
        // console.log('Audio file downloaded successfully');
      } else {
        text = await response.text();
        // console.log('File downloaded successfully');
      }
    } else if (fileObj.file) {
      if (audioFile) {
        blob = fileObj.file;
      } else {
        text = await fileObj.file.text();
      }
    } else {
      throw new Error('No file available to view');
    }

    if (audioFile && blob) {
      const audioUrl = URL.createObjectURL(blob);
      return {
        success: true,
        fileData: { ...fileObj, audioUrl, isAudio: true, isCsv: false, isText: false },
        records: []
      };
    } else if (csvFile) {
      const { headers, records } = parseCSVContent(text);
      return {
        success: true,
        fileData: { ...fileObj, isAudio: false, isCsv: true, isText: false, headers },
        records
      };
    } else {
      return {
        success: true,
        fileData: { ...fileObj, isAudio: false, isCsv: false, isText: true, fullText: text },
        records: []
      };
    }
  } catch (err) {
    console.error("Cannot read or display file:", err);
    toast.error(`Could not open file preview: ${err.message}`);
    return { success: false, error: err.message };
  }
};

/**
 * Loads existing uploaded files for an audit
 */
export const loadExistingFiles = async (auditId, setFiles, setUploadedFile, setIsLoadingFiles) => {
  try {
    setIsLoadingFiles(true);
    // console.log('Loading existing files for audit:', auditId);
    const response = await uploadAPI.listUploadedDatasets(auditId);
    // console.log('Existing files response:', response);

    if (response.uploaded_files && Array.isArray(response.uploaded_files)) {
      const existingFiles = response.uploaded_files.map((fileInfo, index) => ({
        id: `existing-${fileInfo.file_id || index}`,
        name: fileInfo.original_filename || fileInfo.filename,
        serverFilename: fileInfo.filename,
        dataId: fileInfo.data_id,
        progress: 100,
        url: null,
        isExisting: true,
        fileId: fileInfo.file_id,
        fileSize: fileInfo.file_size,
        uploadedAt: fileInfo.uploaded_time
      }));

      setFiles(existingFiles);
      // console.log(`Loaded ${existingFiles.length} existing file(s)`);

      if (existingFiles.length > 0) {
        setUploadedFile({
          serverFilename: existingFiles[0].serverFilename,
          originalFilename: existingFiles[0].name,
          dataId: existingFiles[0].dataId
        });
      }

      return { success: true, files: existingFiles };
    }

    return { success: true, files: [] };
  } catch (error) {
    console.error('Error loading existing files:', error);
    alert(`Failed to load files: ${error.message || 'Unknown error'}`);
    return { success: false, error: error.message };
  } finally {
    setIsLoadingFiles(false);
  }
};

/**
 * Saves outcome evaluation to the server
 */
export const saveOutcomeEvaluation = async (
  auditId,
  results,
  selectedMetricForAnalysis,
  onComplete,
  onSave,
  onClose,
  toast
) => {

  try {
    const eventId = selectedMetricForAnalysis?.event_id || selectedMetricForAnalysis?.eventId;
    const metricId = selectedMetricForAnalysis.metric_id;

    if (!eventId || !metricId) {
      toast.error("Missing event or metric information. Cannot save.");
      return { success: false };
    }

    const batchUpdates = results.map(result => ({
      event_id: parseInt(eventId),
      metric_id: parseInt(metricId),
      data_id: result.dataId,
      meet_requirement: getRecommendation(result.meetMetric),
      notes: result.notes || ""
    }));

    // console.log('Sending batch update:', JSON.stringify(batchUpdates, null, 2));

    await evaluationAPI.saveOutputEvaluationAnalysis(auditId, batchUpdates);

    const summary = calculateEvaluationSummary(results);
    const outcomeData = {
      files: results,
      notes: "Outcome evaluation completed",
      summary
    };

    if (onComplete) {
      onComplete(outcomeData);
    }

    if (onSave) {
      // console.log('Triggering audit data reload after save...');
      await onSave();
    }

    toast.success("Outcome evaluation saved successfully! Audit data has been refreshed.");

    if (onClose) {
      onClose();
    }

    return { success: true, outcomeData };
  } catch (error) {
    console.error("Error saving outcome evaluation:", error);
    toast.error(`Failed to save evaluation: ${error.message || 'Unknown error'}`);
    return { success: false, error: error.message };
  }
};

/**
 * Starts the evaluation process
 */
export const startEvaluation = async (
  auditId,
  files,
  uploadedFile,
  onEvaluationStart,
  setIsEvaluating,
  setEvaluationResult,
  setresults,
  setTabIndex
) => {
  const fileInfo = uploadedFile || (files.length > 0 ? {
    file: files[0].file,
    serverFilename: files[0].serverFilename || files[0].name,
    originalFilename: files[0].name
  } : null);

  if (!fileInfo) {
    alert("Please upload a file before starting evaluation.");
    return { success: false };
  }

  // console.log('Starting evaluation with file:', fileInfo.serverFilename);

  setIsEvaluating(true);
  setEvaluationResult(null);
  setresults([]);

  if (onEvaluationStart) {
    onEvaluationStart();
  }

  try {
    setTabIndex(1);
    // console.log('Calling evaluation API with auditId:', auditId);
    const response = await evaluationAPI.getOutputEvaluationResults(auditId);

    // Handle both old format (response.classifications) and new format (response.output_evaluation)
    const evaluationData = response.classifications || response.output_evaluation;

    if (response.success !== false && evaluationData && evaluationData.length > 0) {
      const results = evaluationData.map((item, index) => {
        const matchingFile = files.find(f =>
          f.serverFilename === item.file_name || f.name === item.file_name
        );

        // Handle output - can be in item.output (new format) or item.classification (old format)
        let output = item.output || '';
        if (!output && item.classification) {
          output = item.classification;
        } else if (!output && item.predicted_subjects) {
          if (typeof item.predicted_subjects === 'string') {
            output = item.predicted_subjects;
          } else if (typeof item.predicted_subjects === 'object' && item.predicted_subjects.classification) {
            output = item.predicted_subjects.classification;
          } else if (typeof item.predicted_subjects === 'object') {
            output = JSON.stringify(item.predicted_subjects);
          }
        }

        // Map requirements number to meetMetric string
        // 0=NotEvaluated (null), 1=No, 2=Maybe, 3=Yes
        const requirementsMap = { 0: null, 1: 'No', 2: 'Maybe', 3: 'Yes' };
        const meetMetric = requirementsMap[item.requirements] ?? null;

        // console.log(`Mapping requirements for ${item.file_name}: requirements=${item.requirements} -> meetMetric=${meetMetric}`);

        // Use data_id if available, otherwise use index + 1 for unique ID
        const uniqueId = item.data_id || item.id || (index + 1);

        return {
          id: uniqueId,
          fileName: item.file_name,
          input: item.metadata || item.file_name,
          output: output,
          meetMetric: meetMetric,
          confidence: item.confidence || (typeof output === 'object' ? output.confidence : null),
          predictedClass: item.predicted_subjects,
          dataId: item.data_id || matchingFile?.dataId,
          notes: item.notes || ''
        };
      });

      setresults(results);

      const totalProcessed = response.total_entries_processed || response.total_output_evaluated || results.length;
      const resultMessage = `Evaluation Complete!\n` +
        `${response.model_name ? `Model: ${response.model_name} (ID: ${response.model_id})\n` : ''}` +
        `Total entries processed: ${totalProcessed}\n`;
      setEvaluationResult(resultMessage);

      return { success: true, results };
    } else {
      throw new Error('Invalid response format from evaluation API');
    }
  } catch (err) {
    console.error("Evaluation error:", err);
    alert(`Evaluation failed: ${err.message || 'Unknown error'}`);
    return { success: false, error: err.message };
  } finally {
    setIsEvaluating(false);
  }
};

/**
 * Transforms API results to the internal results format
 */
export const transformApiResultsToResults = (results) => {
  return results.map(result => {
    const meetMetric = mapMeetRequirementToMetric(result.meet_requirement);

    let outputValue = '';
    if (result.output) {
      if (typeof result.output === 'string') {
        outputValue = result.output;
      } else if (typeof result.output === 'object') {
        if (result.output.classification) {
          outputValue = result.output.classification;
        } else {
          outputValue = JSON.stringify(result.output);
        }
      }
    }

    return {
      id: result.data_id,
      dataId: result.data_id,
      fileName: `Data ${result.data_id}`,
      input: outputValue,
      output: outputValue,
      meetMetric: meetMetric === 'NotEvaluated' ? null : meetMetric,
      notes: result.notes || ''
    };
  });
};
