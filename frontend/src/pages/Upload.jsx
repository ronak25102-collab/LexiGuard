import { useState, useRef, useEffect, useCallback } from 'react';
import { CloudUpload, Cloud, FileText, CheckCircle, Loader, AlertCircle } from 'lucide-react';
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
              'The contract may still be processing â€” refresh the Dashboard to check.'
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
          setError('Processing timeout â€” please check the Dashboard for contract status.');
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
    <div className="h-[calc(100vh-8rem)] w-full bg-transparent text-slate-900 relative overflow-hidden flex flex-col items-center justify-center -my-4">
      <div className="max-w-4xl w-full relative z-10 mx-auto">
        <div className="text-center mb-6">
          <h1 className="text-4xl font-extrabold mb-2 text-slate-900 tracking-tight drop-shadow-sm">
            Upload Contract
          </h1>
          <p className="text-slate-800 text-lg font-semibold">
            Upload a legal contract PDF to analyze and add to the knowledge graph
          </p>
        </div>

        {/* Upload Area (Glassmorphism) */}
        <div
          className={`relative overflow-hidden rounded-3xl py-8 px-6 transition-all duration-500 ease-out group backdrop-blur-xl ${
            dragActive
              ? 'bg-white/50 border border-slate-900/20 shadow-[0_0_50px_-10px_rgba(0,0,0,0.15)] scale-[1.02]'
              : 'bg-white/30 border border-white/50 hover:bg-white/40 hover:border-white/60 shadow-2xl'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          {/* Animated Background Clouds */}
          <div className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-700">
             <Cloud className="absolute text-slate-900/10 w-24 h-24 -top-4 -left-4 animate-[bounce_8s_infinite]" />
             <Cloud className="absolute text-slate-900/10 w-32 h-32 bottom-4 right-10 animate-[bounce_6s_infinite_reverse]" />
             <Cloud className="absolute text-slate-900/10 w-16 h-16 top-10 right-20 animate-[bounce_7s_infinite]" />
          </div>

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
            className="relative flex flex-col items-center justify-center cursor-pointer z-10 scale-90"
          >
            <div className={`relative mb-8 transition-transform duration-500 ${dragActive ? 'scale-125' : 'group-hover:scale-110'}`}>
               {/* Pulsing ring behind the icon when dragging */}
               {dragActive && (
                 <div className="absolute inset-0 bg-slate-900/10 rounded-full animate-ping scale-150" />
               )}
               <CloudUpload className={`w-24 h-24 transition-colors duration-300 drop-shadow-md ${
                 dragActive ? 'text-slate-900 animate-bounce' : 'text-slate-700 group-hover:text-slate-900'
               }`} />
            </div>
            
            <p className="text-2xl font-bold mb-3 text-slate-900 text-center drop-shadow-sm">
              {file ? (
                 <span className="text-slate-900 font-extrabold">
                    {file.name}
                 </span>
              ) : 'Drop your PDF here or click to browse'}
            </p>
            <p className="text-slate-700 text-sm font-semibold tracking-wide">
              {file ? formatFileSize(file.size) : 'Supports PDF files only (Max 10MB)'}
            </p>
          </label>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-6 p-4 backdrop-blur-md bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center gap-3 animate-[pulse_2s_ease-in-out]">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <span className="text-red-700 font-medium">{error}</span>
          </div>
        )}

        {/* Upload Button */}
        {file && !uploadResult && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="mt-4 w-full relative overflow-hidden group bg-slate-900 text-white px-6 py-4 rounded-2xl font-bold text-lg shadow-xl shadow-slate-900/20 hover:bg-slate-800 hover:shadow-2xl hover:shadow-slate-900/30 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 transform hover:-translate-y-1"
          >
            {uploading ? (
              <>
                <Loader className="w-6 h-6 animate-spin text-white" />
                Processing...
              </>
            ) : (
              <>
                <CloudUpload className="w-6 h-6 group-hover:scale-110 transition-transform" />
                Upload & Process Contract
              </>
            )}
          </button>
        )}

        {/* Upload Result (Glassmorphism) */}
        {uploadResult && (
          <div className="mt-10 backdrop-blur-xl bg-white/30 rounded-3xl p-5 border border-white/50 shadow-2xl">
            <div className="flex items-start gap-6">
              <div className="bg-white/50 p-4 rounded-2xl border border-white/50 shadow-inner">
                {uploadResult.status === 'completed' ? (
                  <CheckCircle className="w-10 h-10 text-slate-800 flex-shrink-0 drop-shadow-sm" />
                ) : uploadResult.status === 'not_found' ? (
                  <AlertCircle className="w-10 h-10 text-red-600 flex-shrink-0 drop-shadow-sm" />
                ) : (
                  <Loader className="w-10 h-10 text-slate-800 animate-spin flex-shrink-0 drop-shadow-sm" />
                )}
              </div>

              <div className="flex-1">
                <h3 className="text-2xl font-bold mb-4 text-slate-900">
                  {uploadResult.status === 'completed'
                    ? 'Processing Complete!'
                    : uploadResult.status === 'not_found'
                    ? 'Contract Not Found'
                    : uploadResult.status === 'error'
                    ? 'Processing Failed'
                    : 'Processing...'}
                </h3>

                {/* Progress Bar */}
                {progress > 0 && (
                  <div className="mb-6 bg-white/40 p-5 rounded-2xl border border-white/50 shadow-inner">
                    <div className="flex justify-between text-sm mb-3">
                      <span className="text-slate-700 font-medium">{currentStep}</span>
                      <div className="flex items-center gap-3">
                        {elapsedTime > 0 && (
                          <span className="text-slate-600 text-xs font-medium bg-white/50 px-2 py-1 rounded-md">
                            {formatTime(elapsedTime)}
                            {uploading && progress < 100 && progress > 10 && getEstimatedTimeRemaining(progress, elapsedTime) > 0 && (
                              <span className="text-slate-500"> â€¢ ~{formatTime(getEstimatedTimeRemaining(progress, elapsedTime))} left</span>
                            )}
                          </span>
                        )}
                        <span className="text-slate-900 font-bold bg-slate-900/10 px-2 py-1 rounded-md">{progress}%</span>
                      </div>
                    </div>
                    <div className="w-full bg-white/50 rounded-full h-3 overflow-hidden shadow-inner border border-white/50">
                      <div
                        className={`h-3 rounded-full transition-all duration-500 ease-out relative overflow-hidden ${
                          progress >= 100
                            ? 'bg-slate-800'
                            : 'bg-slate-800'
                        }`}
                        style={{ width: `${progress}%` }}
                      >
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4 text-sm text-slate-700 mb-6">
                  <div className="bg-white/40 p-3 rounded-xl border border-white/50">
                    <span className="block text-slate-500 text-xs mb-1 uppercase tracking-wider">Contract ID</span>
                    <code className="text-slate-800 font-mono">{uploadResult.contract_id}</code>
                  </div>
                  {uploadResult.size_bytes && (
                    <div className="bg-white/40 p-3 rounded-xl border border-white/50">
                      <span className="block text-slate-500 text-xs mb-1 uppercase tracking-wider">File Size</span>
                      <span className="text-slate-800 font-medium">{formatFileSize(uploadResult.size_bytes)}</span>
                    </div>
                  )}
                  <div className="bg-white/40 p-3 rounded-xl border border-white/50 col-span-2">
                    <span className="block text-slate-500 text-xs mb-1 uppercase tracking-wider">Status</span>
                    <span className={`font-bold tracking-wide ${
                        uploadResult.status === 'completed'
                          ? 'text-slate-800'
                          : uploadResult.status === 'processing' || uploadResult.status === 'extracting'
                          ? 'text-slate-700'
                          : uploadResult.status === 'error'
                          ? 'text-red-600'
                          : 'text-amber-600'
                      }`}
                    >
                      {uploadResult.status?.toUpperCase() ?? 'UNKNOWN'}
                    </span>
                  </div>
                </div>

                {uploadResult.status === 'completed' && (
                  <div className="flex gap-4">
                    <a
                      href={`/contract/${uploadResult.graph_id || uploadResult.contract_id}`}
                      className="px-6 py-3 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-slate-900/20"
                    >
                      View Knowledge Graph
                    </a>
                    <a
                      href="/query"
                      className="px-6 py-3 bg-white/40 hover:bg-white/60 text-slate-900 font-semibold rounded-xl transition-colors border border-white/50"
                    >
                      Ask Questions
                    </a>
                  </div>
                )}

                {(uploadResult.status === 'error' || error) && !uploading && (
                  <div className="flex gap-4">
                    <button
                      onClick={() => {
                        setUploadResult(null);
                        setError(null);
                        setFile(null);
                        setProgress(0);
                        setCurrentStep('');
                      }}
                      className="px-6 py-3 bg-white/40 hover:bg-white/60 text-slate-900 font-semibold rounded-xl transition-colors border border-white/50"
                    >
                      Try Again
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Instructions (Glassmorphism) */}
        <div className="mt-6 grid md:grid-cols-3 gap-6">
          <div className="backdrop-blur-md bg-white/30 rounded-3xl p-5 border border-white/50 hover:bg-white/40 transition-colors shadow-xl">
            <div className="w-12 h-12 bg-slate-900/5 rounded-2xl flex items-center justify-center mb-3 border border-slate-900/10 shadow-inner">
              <FileText className="w-6 h-6 text-slate-800" />
            </div>
            <h3 className="font-bold text-lg mb-2 text-slate-900 drop-shadow-sm">1. Upload PDF</h3>
            <p className="text-sm text-slate-700 leading-relaxed">
              Upload any legal contract in PDF format (max 10MB)
            </p>
          </div>

          <div className="backdrop-blur-md bg-white/30 rounded-3xl p-5 border border-white/50 hover:bg-white/40 transition-colors shadow-xl">
            <div className="w-12 h-12 bg-slate-900/5 rounded-2xl flex items-center justify-center mb-3 border border-slate-900/10 shadow-inner">
              <Loader className="w-6 h-6 text-slate-800" />
            </div>
            <h3 className="font-bold text-lg mb-2 text-slate-900 drop-shadow-sm">2. AI Processing</h3>
            <p className="text-sm text-slate-700 leading-relaxed">
              AI extracts parties, clauses, and relationships (2-5 min)
            </p>
          </div>

          <div className="backdrop-blur-md bg-white/30 rounded-3xl p-5 border border-white/50 hover:bg-white/40 transition-colors shadow-xl">
            <div className="w-12 h-12 bg-slate-900/5 rounded-2xl flex items-center justify-center mb-3 border border-slate-900/10 shadow-inner">
              <CheckCircle className="w-6 h-6 text-slate-800" />
            </div>
            <h3 className="font-bold text-lg mb-2 text-slate-900 drop-shadow-sm">3. Query & Analyze</h3>
            <p className="text-sm text-slate-700 leading-relaxed">
              Ask questions about your contract instantly
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}



