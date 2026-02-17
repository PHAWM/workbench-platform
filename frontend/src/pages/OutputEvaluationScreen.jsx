// OutcomeEvaluationScreen.jsx
import React, { useRef, useState, useEffect, useMemo } from "react";
import { Download, Plus, Trash, RefreshCcw, Upload, Search, ChevronLeft, ChevronRight, ArrowLeft } from "lucide-react";
import { performanceAPI, aiApplicationAPI } from "../api/apiService";
import { Tab, Tabs, TabList, TabPanel } from 'react-tabs';
import {
  uploadFileToServer,
  deleteFile,
  downloadFile,
  viewFile,
  loadExistingFiles as loadExistingFilesHandler,
  saveOutcomeEvaluation,
  startEvaluation,
  calculateEvaluationSummary,
  extractInputValue,
  extractOutputValue
} from "../handlers/outcomeEvaluationHandlers";
import { useToast } from '../hooks/useToast';

/**
 * Props:
 * - selectedMetricForAnalysis: the metric object (eventName, name, etc.)
 * - onClose: function to call when user wants to close/back
 * - onStartEvaluation(filesArray): optional callback when Start Evaluation pressed
 * - isReadOnly: boolean to disable editing capabilities
 * - initialEvaluationData: existing evaluation data to restore (optional)
 * - onSave: callback after successfully saving evaluation (optional)
 */
export default function OutcomeEvaluationScreen({
  auditId,
  selectedMetricForAnalysis,
  onClose,
  onEvaluationStart, // Add this new prop
  onComplete, // Add this new prop
  isReadOnly = false, // Add this new prop with default value
  initialEvaluationData = null, // Add this new prop for restoring data
  onSave = null, // Add this new prop for triggering reload after save
  applicationModels = [], // Application models containing input/output type info
}) 
{
  const fileInputRef = useRef(null);
  const [files, setFiles] = useState([]); // { id, file, name, progress, url }
  const [isLoadingFiles, setIsLoadingFiles] = useState(true);
  const hasLoadedFilesRef = useRef(false); // Track if files have been loaded once

  const [showModal, setShowModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileRecords, setFileRecords] = useState([]); // parsed file content

  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [results, setResults] = useState([]); // Store mock evaluation results

  const [tabIndex, setTabIndex] = useState(0);
  const toast = useToast();

  // State for application models (fetched if not provided via props)
  const [fetchedApplicationModels, setFetchedApplicationModels] = useState([]);

  // Use props if provided, otherwise use fetched data
  const effectiveApplicationModels = applicationModels && applicationModels.length > 0
    ? applicationModels
    : fetchedApplicationModels;

  // Search and pagination state for results
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 10;

  // Filter and paginate results
  const filteredResults = useMemo(() => {
    if (!searchQuery.trim()) return results;
    const query = searchQuery.toLowerCase();
    return results.filter(result => {
      // Get input value - could be fileName, metadata object, or string
      const inputValue = result.fileName ||
                        (typeof result.input === 'string' ? result.input :
                        typeof result.input === 'object' ? JSON.stringify(result.input) : '');
      // Get output value - could be classification string or full output object
      const outputValue = typeof result.output === 'string' ? result.output :
                        typeof result.output === 'object' && result.output?.classification ? result.output.classification :
                        typeof result.output === 'object' ? JSON.stringify(result.output) :
                        String(result.output || '');
      return inputValue.toLowerCase().includes(query) ||
             outputValue.toLowerCase().includes(query) ||
             (result.notes || '').toLowerCase().includes(query);
    });
  }, [results, searchQuery]);

  const totalPages = Math.ceil(filteredResults.length / ITEMS_PER_PAGE);
  const paginatedResults = useMemo(() => {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredResults.slice(startIndex, startIndex + ITEMS_PER_PAGE);
  }, [filteredResults, currentPage]);

  // Reset to page 1 when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // Search and pagination state for files
  const [fileSearchQuery, setFileSearchQuery] = useState('');
  const [fileCurrentPage, setFileCurrentPage] = useState(1);
  const FILES_PER_PAGE = 10;

  // Filter and paginate files
  const filteredFiles = useMemo(() => {
    if (!fileSearchQuery.trim()) return files;
    const query = fileSearchQuery.toLowerCase();
    return files.filter(f =>
      f.name.toLowerCase().includes(query) ||
      (f.serverFilename || '').toLowerCase().includes(query)
    );
  }, [files, fileSearchQuery]);

  const fileTotalPages = Math.ceil(filteredFiles.length / FILES_PER_PAGE);
  const paginatedFiles = useMemo(() => {
    const startIndex = (fileCurrentPage - 1) * FILES_PER_PAGE;
    return filteredFiles.slice(startIndex, startIndex + FILES_PER_PAGE);
  }, [filteredFiles, fileCurrentPage]);

  // Reset to page 1 when file search changes
  useEffect(() => {
    setFileCurrentPage(1);
  }, [fileSearchQuery]);

  // helper to open file picker
  const openFilePicker = () => fileInputRef.current?.click();

  // add files from input
  const handleFilesSelected = (e) => {
    const chosen = Array.from(e.target.files || []);
    if (!chosen.length) return;

    const newFiles = chosen.map((f, i) => ({
      id: Date.now() + i,
      file: f,
      name: f.name,
      progress: 0,
      url: null,
    }));

    setFiles((prev) => [...prev, ...newFiles]);
    // upload each new file
    newFiles.forEach((nf) => uploadFileToServer(auditId, nf, setFiles, setUploadedFile, toast));
    e.target.value = ""; // reset input
  };

  const handleDelete = async (fileName) => {
    await deleteFile(auditId, fileName, setFiles, setUploadedFile);
  };

  const handleDownload = async (fileObj) => {
    await downloadFile(auditId, fileObj);
  };

  const handleView = async (fileObj) => {
    const result = await viewFile(auditId, fileObj, toast);
    if (result.success) {
      setSelectedFile(result.fileData);
      setFileRecords(result.records);
      setShowModal(true);
    }
  };

  // Handle Meet Metric selection change - uses uniqueKey for matching
  const handleMeetMetricChange = (uniqueKey, newValue) => {
    setResults(prev =>
      prev.map(result => {
        // Build the same uniqueKey as used in rendering
        const resultKey = result.dataId ?? result.id ?? null;
        // Match by comparing uniqueKey (handles both number and string comparisons)
        const matches = String(resultKey) === String(uniqueKey);
        return matches ? { ...result, meetMetric: newValue } : result;
      })
    );
  };

  // Handle Notes change - uses uniqueKey for matching
  const handleNotesChange = (uniqueKey, newNotes) => {
    setResults(prev =>
      prev.map(result => {
        // Build the same uniqueKey as used in rendering
        const resultKey = result.dataId ?? result.id ?? null;
        // Match by comparing uniqueKey (handles both number and string comparisons)
        const matches = String(resultKey) === String(uniqueKey);
        return matches ? { ...result, notes: newNotes } : result;
      })
    );
  };
// Handle save outcome evaluation
  const handleSaveOutcomeEvaluation = async () => {
    const result = await saveOutcomeEvaluation(
      auditId,
      results,
      selectedMetricForAnalysis,
      onComplete,
      onSave,
      onClose,
      toast
    );
    return result;
  };

  // Handle start evaluation
  const handleStartEvaluation = async () => {
    await startEvaluation(
      auditId,
      files,
      uploadedFile,
      onEvaluationStart,
      setIsEvaluating,
      setEvaluationResult,
      setResults,
      setTabIndex
    );
  };

  // Load existing uploaded files function (can be called manually or in useEffect)
  const loadExistingFiles = async () => {
    await loadExistingFilesHandler(auditId, setFiles, setUploadedFile, setIsLoadingFiles);
  };

  // Load files only once when component mounts
  useEffect(() => {
    if (auditId && !hasLoadedFilesRef.current) {
      // console.log('Initial file list load');
      loadExistingFiles();
      hasLoadedFilesRef.current = true;
    }
  }, [auditId]);

  // Fetch application models if not provided via props
  useEffect(() => {
    const fetchApplicationModels = async () => {
      if (auditId && (!applicationModels || applicationModels.length === 0)) {
        try {
          const auditData = await aiApplicationAPI.getApplicationOverview(auditId);
          // console.log('Fetched audit data for models:', auditData);
          if (auditData?.application_models) {
            // console.log('Application models:', auditData.application_models);
            setFetchedApplicationModels(auditData.application_models);
          }
        } catch (error) {
          console.warn('Failed to fetch application models:', error);
        }
      }
    };
    fetchApplicationModels();
  }, [auditId, applicationModels]);

  // Restore evaluation results from initialEvaluationData when component mounts
  useEffect(() => {
    if (initialEvaluationData && initialEvaluationData.files) {
      // console.log('Restoring evaluation data from memory:', initialEvaluationData);

      // Map requirements to meetMetric if needed (in case data has requirements but not meetMetric)
      const requirementsMap = { 0: null, 1: 'No', 2: 'Maybe', 3: 'Yes' };
      const restoredFiles = initialEvaluationData.files.map(file => {
        // If meetMetric is already set, use it; otherwise map from requirements
        if (file.meetMetric !== undefined) {
          return file;
        }
        const meetMetric = requirementsMap[file.requirements] ?? null;
        // console.log(`Restoring from memory: file=${file.fileName}, requirements=${file.requirements} -> meetMetric=${meetMetric}`);
        return { ...file, meetMetric };
      });

      setResults(restoredFiles);

      // Set evaluation result message if we have results
      if (restoredFiles.length > 0) {
        const resultMessage = `Evaluation Complete!\n` +
          `Total entries processed: ${restoredFiles.length}\n` +
          `(Restored from previous evaluation)`;
        setEvaluationResult(resultMessage);
      }
    }
  }, [initialEvaluationData]);

  // Fetch outcome evaluation results from API on mount
  useEffect(() => {
    const fetchOutcomeEvaluationResults = async () => {
      // Skip if we already have initialEvaluationData (memory takes priority)
      if (initialEvaluationData && initialEvaluationData.files && initialEvaluationData.files.length > 0) {
        // console.log('Skipping API fetch - using initialEvaluationData');
        return;
      }

      // Skip if no metric selected
      if (!selectedMetricForAnalysis || !selectedMetricForAnalysis.metric_id) {
        return;
      }

      try {
        // console.log('Fetching outcome evaluation results for metric:', selectedMetricForAnalysis.metric_id);
        // Use the summary endpoint which includes output_evaluation array
        const response = await performanceAPI.getEvaluationSummary(auditId);

        if (response && response.output_evaluation && response.output_evaluation.length > 0) {
          // Filter results for the current metric using audit_criteria_id
          // The metric's audit_criteria_id should match the output_evaluation's audit_criteria_id
          const criteriaId = selectedMetricForAnalysis.audit_criteria_id || selectedMetricForAnalysis.id;
          const metricResults = response.output_evaluation.filter(
            result => result.audit_criteria_id === criteriaId
          );

          if (metricResults.length > 0) {
            // console.log('Found', metricResults.length, 'results for this metric');

            // Transform API results to results format
            // The new API uses 'requirements' (0=NotEvaluated, 1=No, 2=Maybe, 3=Yes)
            const transformedResults = metricResults.map(result => {
              // Map requirements number to meetMetric string
              const requirementsMap = { 0: null, 1: 'No', 2: 'Maybe', 3: 'Yes' };
              const meetMetric = requirementsMap[result.requirements] ?? null;

              // console.log(`Loading saved result: file=${result.file_name}, requirements=${result.requirements} -> meetMetric=${meetMetric}`);

              return {
                id: result.data_id,
                dataId: result.data_id,
                fileName: result.file_name || `Data ${result.data_id}`,
                fileIndex: result.file_index,
                input: result.metadata || result.target_features || `File ${result.file_index || result.data_id}`,
                output: result.output,
                meetMetric: meetMetric,
                notes: result.notes || '',
                threshold: result.threshold,
                scalePoints: result.scale_points
              };
            });
            setResults(transformedResults);

            // Set evaluation result message
            const summary = calculateEvaluationSummary(transformedResults);
            const resultMessage = `Previous Evaluation Loaded!\n` +
              `Total entries: ${transformedResults.length}\n` +
              `Yes: ${summary.yes} | No: ${summary.no} | Maybe: ${summary.maybe} | Not Evaluated: ${summary.notEvaluated}\n` +
              `(Loaded from database)`;
            setEvaluationResult(resultMessage);

            // Send the loaded results back to parent via onComplete
            if (onComplete) {
              const outcomeData = {
                files: transformedResults,
                notes: "Outcome evaluation loaded from database",
                summary
              };
              onComplete(outcomeData);
            }

            // console.log('Outcome evaluation results loaded from API and sent to parent');
          } else {
            // console.log('No results found for this metric');
          }
        }
      } catch (error) {
        console.warn('Failed to fetch outcome evaluation results:', error);
        // Don't show error to user - this is expected if no evaluations exist yet
      }
    };

    fetchOutcomeEvaluationResults();
  }, [auditId, selectedMetricForAnalysis, initialEvaluationData, onComplete]);

  return (
    <div className="flex flex-col w-full">
      <div className="w-full overflow-auto">
        {/* Purpose Box - Added as per wireframe */}
        <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
          <div className="flex items-start">
            <div>
                <p className="text-gray-700">
                This is Output Evaluation page. The purpose of this page is to allow you to upload your own data and evaluate the output of the AI Application with your data as input and then judge the output against your chosen audit criteria. Once you have uploaded your files in the Upload tab and have decided if the output meets the metric expectations in the Results tab, you can save the analysis by clicking the Save Analysis button or return to the Performance analysis screen of the audit criteria without saving by clicking the Return to Performance Analysis without saving button.
                  </p>
            </div>
          </div>
        </div>
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-800">
              Output Evaluation: {selectedMetricForAnalysis?.eventName} -{" "}
              {selectedMetricForAnalysis?.name}
            </h2>
          </div>
        </div> 
        {/* Tabs */}
        <Tabs selectedIndex={tabIndex} onSelect={(index) => setTabIndex(index)}>
          <TabList>
            <Tab>Upload</Tab>
            <Tab>Results</Tab>
          </TabList>

          {/* Instruction / upload area */}
          <TabPanel>
            <div className="px-1">
              <div className="flex items-start grid grid-cols-2 justify-between">
                <div>
                  <p className="text-base text-gray-600 mt-2">
                    Upload one or multiple files for this evaluation. Acceptable formats based on the AI Application:
                  </p>
                  <ul className="list-disc list-inside text-gray-700 mb-4">
                    {effectiveApplicationModels && effectiveApplicationModels.length > 0 ? (
                      <>
                        {effectiveApplicationModels.map((model, index) => {
                          const modelName = model.name || model.model_name || `Model ${index + 1}`;
                          // Format acceptable_formats array into readable string
                          const acceptableFormats = model.acceptable_formats && model.acceptable_formats.length > 0
                            ? model.acceptable_formats.map(f => `.${f}`).join(',  ')
                            : 'Not specified';
                          const outputContext = model.output_context || 'Not specified';
                          const task = model.task || '';

                          return (
                            <li key={index} className="mb-2">
                              <strong>{modelName}:</strong>{' '}
                              {task}
                              <ul className="ml-4 mt-1 list-none">
                                <li>Acceptable input formats: <span className="font-semibold">{acceptableFormats}</span></li>
                                <li>Output: <span className="font-medium">{outputContext}</span></li>
                              </ul>
                            </li>
                          );
                        })}
                      </>
                    ) : (
                      <>
                        <li>Text files (.txt) or CSV for text data (each input per line/row)</li>
                        <li>CSV files for tabular data</li>
                        <li>Audio or image files for multimedia data</li>
                      </>
                    )}
                    <li className="mt-2 text-purple-700 font-medium">
                      Please include a <code className="bg-purple-100 px-1 rounded">metadata.csv</code> file
                      that maps your input files to their expected outputs or provides additional context for evaluation. The columns should be <code>file_name, true_value</code>
                    </li>
                  </ul>
                </div>
                {/* Upload + Start */}
                  <div className="flex items-end justify-end gap-4">
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      onChange={handleFilesSelected}
                      className="hidden"
                    />
                    {!isReadOnly && (
                      <>
                        <button
                          onClick={loadExistingFiles}
                          disabled={isLoadingFiles}
                          className={`flex items-center gap-2 px-4 py-2 rounded-full font-medium border-2 transition ${
                            isLoadingFiles
                              ? "bg-gray-200 text-gray-500 border-gray-200 cursor-not-allowed"
                              : "bg-purple-100 hover:bg-purple-200 border-purple-200"
                          }`}
                        >
                          <RefreshCcw className="w-4 h-4"/> Reload File List
                        </button>

                        <button
                          onClick={openFilePicker}
                          className="flex items-center gap-2 px-4 py-2 rounded-full bg-purple-100 hover:bg-purple-200 border-2 border-purple-200 font-semibold"
                        >
                          <Upload className="w-4 h-4"/> Add Inputs file
                        </button>

                        <button
                          onClick={handleStartEvaluation}
                          disabled={files.length === 0}
                          className={`flex items-center gap-2 px-4 py-2 rounded-full font-semibold border-2 transition ${
                            files.length === 0
                              ? "bg-gray-200 text-gray-500 border-gray-200 cursor-not-allowed"
                              : "bg-purple-100 hover:bg-purple-200 border-purple-200"
                          }`}
                        >
                          Start Evaluation
                        </button>
                      </>
                    )}
                  </div>
              </div>
              {/* Uploaded files list / upload controls */}
              <div className="border-t border-purple-200 py-6">
                {/* Loading state */}
                {isLoadingFiles && (
                  <div className="text-center py-8 text-gray-600">
                    <div className="animate-spin inline-block w-8 h-8 border-4 border-purple-600 border-t-transparent rounded-full mb-2"></div>
                    <p>Loading existing files...</p>
                  </div>
                )}
                {/* Search Bar for Files */}
                {!isLoadingFiles && files.length > 0 && (
                  <div className="flex-1 grid grid-cols-2 gap-60 mb-6">
                    <div className="flex items-center gap-4">
                      <div className="relative flex-1 max-w-2xl">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type="text"
                          value={fileSearchQuery}
                          onChange={(e) => setFileSearchQuery(e.target.value)}
                          placeholder="Search files by name..."
                          className="w-full pl-10 pr-4 py-2 border-2 border-purple-200 rounded-full text-base focus:outline-none focus:border-purple-400"
                        />
                      </div>
                      <span className="text-base text-gray-600">
                        Showing {filteredFiles.length} of {files.length} files
                      </span>
                    </div>
                    {/* Pagination Controls for Files */}
                    {!isLoadingFiles && fileTotalPages > 1 && (
                    <div className="flex items-center justify-end">
                      <span className="text-base text-gray-600 m-2">
                        Page {fileCurrentPage} of {fileTotalPages}
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setFileCurrentPage(prev => Math.max(prev - 1, 1))}
                          disabled={fileCurrentPage === 1}
                          className={`flex items-center gap-1 px-3 py-1.5 rounded-full border-2 text-base font-medium transition ${
                            fileCurrentPage === 1
                              ? 'border-gray-200 text-gray-400 cursor-not-allowed'
                              : 'border-purple-200 text-purple-700 hover:bg-purple-100'
                          }`}
                        >
                          <ChevronLeft className="w-4 h-4" /> Previous
                        </button>
                        {/* Page numbers */}
                        <div className="flex items-center gap-1">
                          {Array.from({ length: fileTotalPages }, (_, i) => i + 1)
                            .filter(page => {
                              return page === 1 || page === fileTotalPages ||
                                    Math.abs(page - fileCurrentPage) <= 1;
                            })
                            .map((page, idx, arr) => (
                              <React.Fragment key={page}>
                                {idx > 0 && arr[idx - 1] !== page - 1 && (
                                  <span className="px-2 text-gray-400">...</span>
                                )}
                                <button
                                  onClick={() => setFileCurrentPage(page)}
                                  className={`w-8 h-8 rounded-full text-base font-medium transition ${
                                    fileCurrentPage === page
                                      ? 'bg-purple-600 text-white'
                                      : 'border-2 border-purple-200 text-purple-700 hover:bg-purple-100'
                                  }`}
                                >
                                  {page}
                                </button>
                              </React.Fragment>
                            ))}
                        </div>
                        <button
                          onClick={() => setFileCurrentPage(prev => Math.min(prev + 1, fileTotalPages))}
                          disabled={fileCurrentPage === fileTotalPages}
                          className={`flex items-center gap-1 px-3 py-1.5 rounded-full border-2 text-base font-medium transition ${
                            fileCurrentPage === fileTotalPages
                              ? 'border-gray-200 text-gray-400 cursor-not-allowed'
                              : 'border-purple-200 text-purple-700 hover:bg-purple-100'
                          }`}
                        >
                          Next <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    )}
                  </div>
                )}
                {/* Files list */}
                {!isLoadingFiles && files.length > 0 ? (
                  <div className="space-y-4">
                    {paginatedFiles.length > 0 ? paginatedFiles.map((f) => (
                      <div
                        key={f.id}
                        className="flex items-center justify-between bg-purple-50 border border-purple-100 rounded-lg p-4"
                      >
                        <div className="flex items-center gap-4">
                          <div className="text-purple-600 text-3xl">📄</div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="font-medium text-gray-800 truncate">{f.name}</p>
                              {f.isExisting && (
                                <span className="px-2 py-0.5 text-base bg-green-100 text-green-700 rounded-full">
                                  Already uploaded
                                </span>
                              )}
                            </div>
                            {f.serverFilename && f.serverFilename !== f.name && (
                              <p className="text-base text-gray-500 mt-1">Server: {f.serverFilename}</p>
                            )}
                            <div className="w-full bg-purple-100 rounded-full h-2 mt-2">
                              <div
                                className="bg-purple-500 h-2 rounded-full transition-all"
                                style={{ width: `${f.progress}%` }}
                              />
                            </div>
                            <p className="text-base text-gray-500 mt-1">{f.progress}% uploaded</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleView(f)}
                            className="flex items-center gap-1 px-4 py-2 rounded-full bg-white border-2 border-purple-200 font-medium hover:bg-purple-50"
                          >
                              <Plus className="w-4 h-4" /> View
                          </button>
                          {f.isExisting && f.serverFilename && (
                            <button
                              onClick={() => handleDownload(f)}
                              className="flex items-center gap-1 px-4 py-2 rounded-full bg-white border-2 border-purple-200 font-medium hover:bg-blue-50 text-blue-600"
                            >
                              <Download className="w-4 h-4" /> Download
                            </button>
                          )}
                          {!isReadOnly && (
                            <button
                              onClick={() => handleDelete(f.serverFilename)}
                              className="flex items-center gap-1 px-4 py-2 rounded-full bg-white border-2 border-purple-200 font-medium hover:bg-red-50 text-red-600"
                            >
                              <Trash className="w-4 h-4" /> Delete
                            </button>
                          )}
                        </div>
                      </div>
                    )) : (
                      <div className="py-8 text-center text-gray-500">
                        No files match your search.
                      </div>
                    )}
                  </div>
                ) : !isLoadingFiles ? (
                  <div className="py-8 text-gray-600 italic">No files uploaded yet.</div>
                ) : null}
                
              </div>
            </div>
          </TabPanel>
          {/* Evaluation result area */}
          <TabPanel>
              {isEvaluating ? (
                <div>
                  <div className="flex flex-col items-center justify-center h-72 text-center text-gray-600">
                    <p className="text-lg font-medium">Please be patient.</p>
                    <p className="text-base">We are currently retrieving your outputs</p>
                    <div className="w-1/3 mt-6">
                      <div className="w-full bg-gray-100 rounded-full h-3">
                        <div
                          className="bg-blue-300 h-3 rounded-full animate-pulse"
                          style={{ width: "40%" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : (evaluationResult || results.length > 0) ? (
                // Show result after evaluation completes or if cached results exist
                <div>
                  <div className="border-t border-purple-200 pt-4">
                    {/* Search Bar */}
                    {results.length > 0 && (
                      <div className="flex-1 grid grid-cols-2 gap-60 mb-6">
                        <div className="flex items-center gap-4">
                          <div className="relative flex-1 max-w-2xl">
                            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <input
                              type="text"
                              value={searchQuery}
                              onChange={(e) => setSearchQuery(e.target.value)}
                              placeholder="Search by input, output, or notes..."
                              className="w-full pl-10 pr-4 py-2 border-2 border-purple-200 rounded-full text-base focus:outline-none focus:border-purple-400"
                            />
                          </div>
                          <span className="text-base text-gray-600">
                            Showing {filteredResults.length} of {results.length} results
                          </span>
                        </div>
                        {totalPages > 1 && (
                          <div className="flex items-center justify-end mb-6">
                            <span className="text-base text-gray-600">
                              Page {currentPage} of {totalPages}
                            </span>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                disabled={currentPage === 1}
                                className={`flex items-center gap-1 px-3 py-1.5 rounded-full border-2 text-base font-medium transition ${
                                  currentPage === 1
                                    ? 'border-gray-200 text-gray-400 cursor-not-allowed'
                                    : 'border-purple-200 text-purple-700 hover:bg-purple-100'
                                }`}
                              >
                                <ChevronLeft className="w-4 h-4" /> Previous
                              </button>
                              {/* Page numbers */}
                              <div className="flex items-center gap-1">
                                {Array.from({ length: totalPages }, (_, i) => i + 1)
                                  .filter(page => {
                                    // Show first, last, current, and neighbors
                                    return page === 1 || page === totalPages ||
                                          Math.abs(page - currentPage) <= 1;
                                  })
                                  .map((page, idx, arr) => (
                                    <React.Fragment key={page}>
                                      {idx > 0 && arr[idx - 1] !== page - 1 && (
                                        <span className="px-2 text-gray-400">...</span>
                                      )}
                                      <button
                                        onClick={() => setCurrentPage(page)}
                                        className={`w-8 h-8 rounded-full text-base font-medium transition ${
                                          currentPage === page
                                            ? 'bg-purple-600 text-white'
                                            : 'border-2 border-purple-200 text-purple-700 hover:bg-purple-100'
                                        }`}
                                      >
                                        {page}
                                      </button>
                                    </React.Fragment>
                                  ))}
                              </div>
                              <button
                                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                                disabled={currentPage === totalPages}
                                className={`flex items-center gap-1 px-3 py-1.5 rounded-full border-2 text-base font-medium transition ${
                                  currentPage === totalPages
                                    ? 'border-gray-200 text-gray-400 cursor-not-allowed'
                                    : 'border-purple-200 text-purple-700 hover:bg-purple-100'
                                }`}
                              >
                                Next <ChevronRight className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {/* Results Table - ONE RECORD PER FILE */}
                    {results.length > 0 && (
                      <div className="bg-white border-2 border-purple-200 rounded-2xl overflow-hidden mb-4">
                        <table className="w-full">
                          <thead className="bg-purple-100">
                            <tr>
                              <th className="px-6 py-3 text-left text-base font-semibold text-gray-800 border-r border-purple-200">
                                Input File
                              </th>
                              <th className="px-6 py-3 text-left text-base font-semibold text-gray-800 border-r border-purple-200">
                                AI Application Output
                              </th>
                              <th className="px-6 py-3 text-left text-base font-semibold text-gray-800 border-r border-purple-200">
                                Does Output meet metric expectations?
                              </th>
                              <th className="px-6 py-3 text-left text-base font-semibold text-gray-800">
                                Feedback and Justification
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-purple-100">
                            {paginatedResults.length > 0 ? paginatedResults.map((result, index) => {
                              // Use dataId first (from API), then id, then index as fallback
                              const uniqueKey = result.dataId ?? result.id ?? `row-${index}`;
                              return (
                                <tr key={uniqueKey} className="hover:bg-purple-50">
                                  <td className="px-6 py-4 text-base text-gray-800 border-r border-purple-200">
                                    {result.fileName || result.output?.file_name || extractInputValue(result.input)}
                                  </td>
                                  <td className="px-6 py-4 text-base text-gray-800 border-r border-purple-200">
                                    {extractOutputValue(result.output)}
                                  </td>
                                <td className="px-6 py-4 text-base border-r border-purple-200">
                                  <div className="flex items-center gap-4">
                                    {/* Yes */}
                                    <label className="flex items-center gap-2 text-gray-800">
                                      Yes
                                      <input
                                        type="radio"
                                        name={`meetMetric-${uniqueKey}`}
                                        value="Yes"
                                        checked={result.meetMetric === "Yes"}
                                        onChange={(e) => handleMeetMetricChange(uniqueKey, e.target.value)}
                                        disabled={isReadOnly}
                                        className="text-purple-600 focus:ring-purple-400"
                                      />
                                    </label>

                                    {/* No */}
                                    <label className="flex items-center gap-2 text-gray-800">
                                      No
                                      <input
                                        type="radio"
                                        name={`meetMetric-${uniqueKey}`}
                                        value="No"
                                        checked={result.meetMetric === "No"}
                                        onChange={(e) => handleMeetMetricChange(uniqueKey, e.target.value)}
                                        disabled={isReadOnly}
                                        className="text-purple-600 focus:ring-purple-400"
                                      />
                                    </label>

                                    {/* Maybe */}
                                    <label className="flex items-center gap-2 text-gray-800">
                                      Maybe
                                      <input
                                        type="radio"
                                        name={`meetMetric-${uniqueKey}`}
                                        value="Maybe"
                                        checked={result.meetMetric === "Maybe"}
                                        onChange={(e) => handleMeetMetricChange(uniqueKey, e.target.value)}
                                        disabled={isReadOnly}
                                        className="text-purple-600 focus:ring-purple-400"
                                      />
                                    </label>
                                  </div>
                                </td>

                                <td className="px-6 py-4 text-base text-gray-800 w-third">
                                  <textarea
                                    value={result.notes || ''}
                                    onChange={(e) => handleNotesChange(uniqueKey, e.target.value)}
                                    disabled={isReadOnly}
                                    rows={1}
                                    className={`w-full border-2 border-purple-200 rounded-lg px-3 py-1 text-base focus:outline-none focus:border-purple-400 resize-y ${
                                      isReadOnly ? 'bg-gray-100 cursor-not-allowed' : ''
                                    }`}
                                    placeholder={isReadOnly ? "" : "Enter Feedback..."}
                                  />
                                </td>
                              </tr>
                              );
                            }) : (
                              <tr>
                                <td colSpan={4} className="px-6 py-8 text-center text-gray-500">
                                  No results match your search.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}
                    
                  </div>
                </div>
              ) : (
                // Empty state before evaluation starts
                <div className="text-center text-gray-500 py-10">
                  <p>No evaluation results yet.</p>
                </div>
              )}
          </TabPanel>
        </Tabs>

        <div className="flex items-start justify-between mb-6">
          {/* Back to analysis (close) */}
          <button
            onClick={onClose}
            className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
          >
            <ArrowLeft className="w-4 h-4" />
            Return to Performance Analysis without saving button
          </button>
          {!isReadOnly && (evaluationResult || results.length > 0) &&  (
            <button
              onClick={handleSaveOutcomeEvaluation}
              className="px-6 py-3 rounded-full bg-purple-100 hover:bg-purple-200 border-2 border-purple-200 font-semibold"
            >
              Save Output Evaluation
            </button>
          )}
        </div>
      </div>
      {/* View Modal */}
      {showModal && selectedFile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[999] p-4">
          <div className="bg-white rounded-2xl border-2 border-purple-200 p-8 w-[700px] shadow-lg">
            {/* Header */}
            <h2 className="text-lg font-semibold text-purple-800 mb-2">
              {selectedFile.name}
            </h2>
            <p className="text-gray-600 text-base mb-4">
              {selectedFile.isAudio
                ? 'Audio file preview'
                : selectedFile.isCsv
                ? 'CSV file preview - showing data in table format'
                : selectedFile.isText
                ? 'Text file preview - if you need to edit, please upload a new file'
                : 'File preview'}
            </p>

            {/* Audio Player for WAV/Audio files */}
            {selectedFile.isAudio && selectedFile.audioUrl && (
              <div className="mb-6 p-6 bg-purple-50 rounded-xl border-2 border-purple-200">
                <div className="flex items-center justify-center mb-4">
                  <span className="text-4xl">🎵</span>
                </div>
                <audio
                  controls
                  className="w-full"
                  onError={(e) => {
                    toast.error('Unable to play audio file. The file format may not be supported.');
                  }}
                >
                  <source
                    src={selectedFile.audioUrl}
                    type={`audio/${selectedFile.name?.split('.').pop()}`}
                  />
                  Your browser does not support the audio element.
                </audio>
                <p className="text-base text-gray-500 text-center mt-3">
                  File: {selectedFile.name}
                </p>
              </div>
            )}

            {/* CSV Table view */}
            {selectedFile.isCsv && fileRecords.length > 0 && selectedFile.headers && (
              <div className="max-h-[500px] overflow-auto bg-white rounded-xl border-2 border-purple-200">
                <table className="w-full text-base">
                  <thead className="bg-purple-100 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left font-semibold text-gray-800 border-r border-purple-200">#</th>
                      {selectedFile.headers.map((header, idx) => (
                        <th key={idx} className="px-4 py-2 text-left font-semibold text-gray-800 border-r border-purple-200 last:border-r-0">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-purple-100">
                    {fileRecords.map((record, rowIdx) => (
                      <tr key={record.id} className="hover:bg-purple-50">
                        <td className="px-4 py-2 text-gray-600 border-r border-purple-100 font-medium">{rowIdx + 1}</td>
                        {selectedFile.headers.map((header, colIdx) => (
                          <td key={colIdx} className="px-4 py-2 text-gray-800 border-r border-purple-100 last:border-r-0">
                            {record[header]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Text file view - show whole content */}
            {selectedFile.isText && selectedFile.fullText && (
              <div className="max-h-[500px] overflow-y-auto bg-white rounded-xl border-2 border-purple-200 p-4">
                <pre className="whitespace-pre-wrap text-base text-gray-800 font-mono">
                  {selectedFile.fullText}
                </pre>
              </div>
            )}

            {/* Empty state */}
            {!selectedFile.isAudio && !selectedFile.isCsv && !selectedFile.isText && (
              <div className="text-center py-10 text-gray-500">
                <p>No content to display</p>
              </div>
            )}

            {/* Close button */}
            <div className="flex justify-center mt-6">
              <button
                onClick={() => {
                  if (selectedFile.audioUrl) URL.revokeObjectURL(selectedFile.audioUrl);
                  setShowModal(false);
                }}
                className="flex-1 max-w-[150px] px-5 py-2.5 bg-purple-100 border-2 border-purple-200 text-purple-800 font-semibold rounded-full hover:bg-purple-200 transition-all duration-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}