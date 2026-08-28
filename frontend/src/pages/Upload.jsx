import { useState, useRef, useEffect, useCallback } from 'react';
import { Upload as UploadIcon, FileText, CheckCircle, Loader, AlertCircle } from 'lucide-react';
import { uploadContract, checkContractStatus } from '../api/client';

export default function Upload() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);

  // Refs for interval/timeout cleanup and stale-closure avoidance
  const pollIntervalRef = useRef(null);
  const timeIntervalRef = useRef(null);
  const timeoutRef = useRef(null);
  const uploadingRef = useRef(false);         // mirrors `uploading` for closures
  const pollErrorCountRef = useRef(0);        // track consecutive poll failures
  const startTimeRef = useRef(null);

  const MAX_POLL_ERRORS = 5;   // tolerate up to 5 consecutive poll failures
  const POLL_INTERVAL_MS = 2500;
  const TIMEOUT_MS = 600000;   // 10 minutes

  // Keep the ref in sync with state
  useEffect(() => {
    uploadingRef.current = uploading;
  }, [uploading]);

  // Cleanup all timers on unmount
  useEffect(() => {
    return () => {
      clearInterval(pollIntervalRef.current);
      clearInterval(timeIntervalRef.current);
      clearTimeout(timeoutRef.current);
    };
  }, []);

  /** Tear down every running timer. */
  const stopAllTimers = useCallback(() => {
    clearInterval(pollIntervalRef.current);
    clearInterval(timeIntervalRef.current);
    clearTimeout(timeoutRef.current);
    pollIntervalRef.current = null;
    timeIntervalRef.current = null;
    timeoutRef.current = null;
  }, []);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === 'application/pdf') {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Please upload a PDF file');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type === 'application/pdf') {
        setFile(selectedFile);
        setError(null);
      } else {
        setError('Please upload a PDF file');
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    console.log('Starting upload...', file.name);
    setUploading(true);
    setError(null);
    setUploadResult(null);
    setProgress(5);
    setCurrentStep('Uploading file...');
    const uploadStartTime = Date.now();
    startTimeRef.current = uploadStartTime;
    setElapsedTime(0);
    pollErrorCountRef.current = 0;

    try {
      console.log('Calling uploadContract API...');
      const result = await uploadContract(file);
      console.log('Upload API response:', result);
      setUploadResult(result);
      setProgress(10);
      setCurrentStep('File uploaded. Initializing processing...');
      
      // Start elapsed time counter
      timeIntervalRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - uploadStartTime) / 1000));
      }, 1000);
      
      // Poll for status
      const contractId = result.contract_id;
      pollIntervalRef.current = setInterval(async () => {
        // Guard: if we already stopped, don't run
        if (!uploadingRef.current) return;

        try {
          const status = await checkContractStatus(contractId);
          // Reset error counter on success
          pollErrorCountRef.current = 0;

          setUploadResult(prev => ({ ...prev, ...status }));
          
          // Update progress from backend
          if (status.progress !== undefined) {
            setProgress(status.progress);
          }
          
          if (status.message) {
            setCurrentStep(status.message);
          }
          
          if (status.status === 'completed') {
            stopAllTimers();
            setProgress(100);
            setUploading(false);
          } else if (status.status === 'error' || status.status === 'not_found') {
            stopAllTimers();
            setError(status.message || 'Processing failed');
            setUploading(false);
          }
        } catch (err) {
          pollErrorCountRef.current += 1;
          console.error(
            `Error polling status (${pollErrorCountRef.current}/${MAX_POLL_ERRORS}):`,
            err
          );

          // Tolerate transient failures; only bail after MAX_POLL_ERRORS
          if (pollErrorCountRef.current >= MAX_POLL_ERRORS) {
            stopAllTimers();
            setError(
              `Lost connection to server after ${MAX_POLL_ERRORS} retries. ` +
              'The contract may still be processing — refresh the Dashboard to check.'
            );
            setUploading(false);
          }
        }
      }, POLL_INTERVAL_MS);

      // Stop polling after 10 minutes
      timeoutRef.current = setTimeout(() => {
        // Use the ref to check current uploading state (avoids stale closure)
        if (uploadingRef.current) {
          stopAllTimers();
          setError('Processing timeout — please check the Dashboard for contract status.');
          setUploading(false);
        }
      }, TIMEOUT_MS);

    } catch (err) {
      setError(err.message || 'Failed to upload contract');
      setUploading(false);
      setProgress(0);
      setCurrentStep('');
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getEstimatedTimeRemaining = (currentProgress, elapsedSeconds) => {
    if (currentProgress <= 0 || currentProgress >= 100) return null;
    
    // Estimate based on typical processing time
    // Typically: 10% = 5s, 25% = 15s, 50% = 120s, 85% = 240s, 100% = 300s
    const typicalTimes = {
      10: 5,
      25: 15,
      50: 120,
      85: 240,
      100: 300
    };
    
    // Find next milestone
    let nextTime = 300;
    for (const [milestone, time] of Object.entries(typicalTimes)) {
      if (currentProgress < parseInt(milestone)) {
        nextTime = time;
        break;
      }
    }
    
    // Simple estimate: remaining time = (remaining progress / progress rate)
    if (elapsedSeconds > 0 && currentProgress > 5) {
      const progressRate = currentProgress / elapsedSeconds; // % per second
      const remainingProgress = 100 - currentProgress;
      const estimatedSeconds = remainingProgress / progressRate;
      return Math.max(30, Math.min(300, Math.floor(estimatedSeconds))); // Between 30s and 5min
    }
    
    // Fallback to typical time
    return nextTime - elapsedSeconds;
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
          Upload Contract
        </h1>
        <p className="text-gray-400 mb-8">
          Upload a legal contract PDF to analyze and add to the knowledge graph
        </p>

        {/* Upload Area */}
        <div
          className={`relative border-2 border-dashed rounded-xl p-12 transition-all duration-300 ${
            dragActive
              ? 'border-blue-500 bg-blue-500/10'
              : 'border-gray-600 bg-gray-800/50 hover:border-gray-500'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="hidden"
            id="file-upload"
            disabled={uploading}
          />

          <label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center cursor-pointer"
          >
            <UploadIcon className="w-16 h-16 text-gray-400 mb-4" />
            <p className="text-xl font-semibold mb-2">
              {file ? file.name : 'Drop your PDF here or click to browse'}
            </p>
            <p className="text-gray-400 text-sm">
              {file ? formatFileSize(file.size) : 'Supports PDF files only'}
            </p>
          </label>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-4 bg-red-500/20 border border-red-500 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-400">{error}</span>
          </div>
        )}

        {/* Upload Button */}
        {file && !uploadResult && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="mt-6 w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white px-6 py-4 rounded-lg font-semibold hover:from-blue-600 hover:to-purple-700 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
          >
            {uploading ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <UploadIcon className="w-5 h-5" />
                Upload & Process Contract
              </>
            )}
          </button>
        )}

        {/* Upload Result */}
        {uploadResult && (
          <div className="mt-8 bg-gray-800/80 rounded-xl p-6 border border-gray-700">
            <div className="flex items-start gap-4">
              {uploadResult.status === 'completed' ? (
                <CheckCircle className="w-8 h-8 text-green-400 flex-shrink-0" />
              ) : uploadResult.status === 'not_found' ? (
                <AlertCircle className="w-8 h-8 text-red-400 flex-shrink-0" />
              ) : (
                <Loader className="w-8 h-8 text-blue-400 animate-spin flex-shrink-0" />
              )}

              <div className="flex-1">
                <h3 className="text-xl font-semibold mb-2">
                  {uploadResult.status === 'completed'
                    ? 'Processing Complete!'
                    : uploadResult.status === 'not_found'
                    ? 'Contract Not Found'
                    : uploadResult.status === 'error'
                    ? 'Processing Failed'
                    : 'Processing...'}
                </h3>

                {/* Progress Bar — show while uploading OR right after completion */}
                {progress > 0 && (
                  <div className="mb-4">
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400">{currentStep}</span>
                      <div className="flex items-center gap-3">
                        {elapsedTime > 0 && (
                          <span className="text-gray-500 text-xs">
                            {formatTime(elapsedTime)}
                            {uploading && progress < 100 && progress > 10 && getEstimatedTimeRemaining(progress, elapsedTime) > 0 && (
                              <span className="text-gray-600"> • ~{formatTime(getEstimatedTimeRemaining(progress, elapsedTime))} left</span>
                            )}
                          </span>
                        )}
                        <span className="text-blue-400 font-semibold">{progress}%</span>
                      </div>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-2.5 rounded-full transition-all duration-500 ease-out relative overflow-hidden ${
                          progress >= 100
                            ? 'bg-green-500'
                            : 'bg-gradient-to-r from-blue-500 to-purple-600'
                        }`}
                        style={{ width: `${progress}%` }}
                      >
                        {uploading && progress < 100 && (
                          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-30 animate-shimmer" />
                        )}
                      </div>
                    </div>
                    {uploading && progress >= 50 && progress < 90 && (
                      <p className="text-xs text-gray-500 mt-2">
                        ⏱️ AI analysis typically takes 2-5 minutes for complex contracts
                      </p>
                    )}
                  </div>
                )}

                <div className="space-y-2 text-sm text-gray-300">
                  <p>
                    <span className="text-gray-400">Contract ID:</span>{' '}
                    <code className="bg-gray-700 px-2 py-1 rounded">{uploadResult.contract_id}</code>
                  </p>
                  {uploadResult.filename && (
                    <p>
                      <span className="text-gray-400">Filename:</span> {uploadResult.filename}
                    </p>
                  )}
                  {uploadResult.size_bytes && (
                    <p>
                      <span className="text-gray-400">Size:</span>{' '}
                      {formatFileSize(uploadResult.size_bytes)}
                    </p>
                  )}
                  <p>
                    <span className="text-gray-400">Status:</span>{' '}
                    <span
                      className={`font-semibold ${
                        uploadResult.status === 'completed'
                          ? 'text-green-400'
                          : uploadResult.status === 'processing' || uploadResult.status === 'extracting'
                          ? 'text-blue-400'
                          : uploadResult.status === 'error'
                          ? 'text-red-400'
                          : 'text-yellow-400'
                      }`}
                    >
                      {uploadResult.status?.toUpperCase() ?? 'UNKNOWN'}
                    </span>
                  </p>
                  {uploadResult.title && (
                    <p>
                      <span className="text-gray-400">Title:</span> {uploadResult.title}
                    </p>
                  )}
                </div>

                {uploadResult.status === 'completed' && (
                  <div className="mt-4 flex gap-3">
                    <a
                      href={`/contract/${uploadResult.graph_id || uploadResult.contract_id}`}
                      className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                    >
                      View Contract
                    </a>
                    <a
                      href="/query"
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                    >
                      Ask Questions
                    </a>
                  </div>
                )}

                {(uploadResult.status === 'error' || error) && !uploading && (
                  <div className="mt-4 flex gap-3">
                    <button
                      onClick={() => {
                        setUploadResult(null);
                        setError(null);
                        setFile(null);
                        setProgress(0);
                        setCurrentStep('');
                      }}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                    >
                      Try Again
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-12 grid md:grid-cols-3 gap-6">
          <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
            <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center mb-4">
              <FileText className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="font-semibold mb-2">1. Upload PDF</h3>
            <p className="text-sm text-gray-400">
              Upload any legal contract in PDF format (max 10MB)
            </p>
          </div>

          <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
            <div className="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center mb-4">
              <Loader className="w-6 h-6 text-purple-400" />
            </div>
            <h3 className="font-semibold mb-2">2. AI Processing</h3>
            <p className="text-sm text-gray-400">
              AI extracts parties, clauses, and relationships (2-5 min)
            </p>
          </div>

          <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
            <div className="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center mb-4">
              <CheckCircle className="w-6 h-6 text-green-400" />
            </div>
            <h3 className="font-semibold mb-2">3. Query & Analyze</h3>
            <p className="text-sm text-gray-400">
              Ask questions about your contract instantly
            </p>
          </div>
        </div>

        {/* Tips Section */}
        <div className="mt-8 bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
          <h3 className="font-semibold text-blue-300 mb-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            Pro Tips
          </h3>
          <ul className="text-sm text-gray-300 space-y-2">
            <li>• <strong>Best results:</strong> Use high-quality, text-based PDFs (not scanned images)</li>
            <li>• <strong>Processing time:</strong> Typical contracts take 2-5 minutes to analyze</li>
            <li>• <strong>Stay on page:</strong> Keep this tab open during processing for live updates</li>
            <li>• <strong>Complex contracts:</strong> Large contracts with many clauses may take longer</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
