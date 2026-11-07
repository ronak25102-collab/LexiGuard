import { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowUp, CheckCircle, FileText, RotateCcw } from 'lucide-react';
import { uploadContract, checkContractStatus } from '../api/client';
import PageHeader from '../components/PageHeader';
import Reveal from '../components/Reveal';
import Button from '../components/Button';

// Backend stages and the progress value each one reports when it starts.
const STAGES = [
  ['Upload received', 10],
  ['Parse PDF to text', 25],
  ['Embed for semantic search', 40],
  ['Extract parties and clauses', 50],
  ['Build the knowledge graph', 85],
  ['Ready to query', 100],
];

export default function Upload() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [peakProgress, setPeakProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);

  // Refs for interval/timeout cleanup and stale-closure avoidance
  const pollIntervalRef = useRef(null);
  const timeIntervalRef = useRef(null);
  const timeoutRef = useRef(null);
  const uploadingRef = useRef(false);
  const pollErrorCountRef = useRef(0);
  const startTimeRef = useRef(null);

  const MAX_POLL_ERRORS = 5;
  const POLL_INTERVAL_MS = 2500;
  const TIMEOUT_MS = 600000; // 10 minutes

  useEffect(() => { uploadingRef.current = uploading; }, [uploading]);

  // The backend reports progress 0 on error; remember how far it got.
  useEffect(() => { setPeakProgress(prev => Math.max(prev, progress)); }, [progress]);

  useEffect(() => () => {
    clearInterval(pollIntervalRef.current);
    clearInterval(timeIntervalRef.current);
    clearTimeout(timeoutRef.current);
  }, []);

  const stopAllTimers = useCallback(() => {
    clearInterval(pollIntervalRef.current);
    clearInterval(timeIntervalRef.current);
    clearTimeout(timeoutRef.current);
    pollIntervalRef.current = null;
    timeIntervalRef.current = null;
    timeoutRef.current = null;
  }, []);

  const acceptFile = (candidate) => {
    if (candidate.type === 'application/pdf') {
      setFile(candidate);
      setError(null);
    } else {
      setError('Please upload a PDF file');
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (uploading) return;
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (uploading) return;
    if (e.dataTransfer.files && e.dataTransfer.files[0]) acceptFile(e.dataTransfer.files[0]);
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) acceptFile(e.target.files[0]);
  };

  const reset = () => {
    setUploadResult(null);
    setError(null);
    setFile(null);
    setProgress(0);
    setPeakProgress(0);
    setCurrentStep('');
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadResult(null);
    setProgress(5);
    setPeakProgress(5);
    setCurrentStep('Uploading file…');
    const uploadStartTime = Date.now();
    startTimeRef.current = uploadStartTime;
    setElapsedTime(0);
    pollErrorCountRef.current = 0;

    try {
      const result = await uploadContract(file);
      setUploadResult(result);
      setProgress(10);
      setCurrentStep('File uploaded. Initializing processing…');

      timeIntervalRef.current = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - uploadStartTime) / 1000));
      }, 1000);

      const contractId = result.contract_id;
      pollIntervalRef.current = setInterval(async () => {
        if (!uploadingRef.current) return;
        try {
          const status = await checkContractStatus(contractId);
          pollErrorCountRef.current = 0;
          setUploadResult(prev => ({ ...prev, ...status }));
          if (status.progress !== undefined) setProgress(status.progress);
          if (status.message) setCurrentStep(status.message);

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
          console.error(`Error polling status (${pollErrorCountRef.current}/${MAX_POLL_ERRORS}):`, err);
          if (pollErrorCountRef.current >= MAX_POLL_ERRORS) {
            stopAllTimers();
            setError(
              `Lost connection to server after ${MAX_POLL_ERRORS} retries. ` +
              'The contract may still be processing. Refresh the Dashboard to check.'
            );
            setUploading(false);
          }
        }
      }, POLL_INTERVAL_MS);

      timeoutRef.current = setTimeout(() => {
        if (uploadingRef.current) {
          stopAllTimers();
          setError('Processing timed out. Check the Dashboard for the contract status.');
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
    const typicalTimes = { 10: 5, 25: 15, 50: 120, 85: 240, 100: 300 };
    let nextTime = 300;
    for (const [milestone, time] of Object.entries(typicalTimes)) {
      if (currentProgress < parseInt(milestone)) { nextTime = time; break; }
    }
    if (elapsedSeconds > 0 && currentProgress > 5) {
      const progressRate = currentProgress / elapsedSeconds;
      const estimatedSeconds = (100 - currentProgress) / progressRate;
      return Math.max(30, Math.min(300, Math.floor(estimatedSeconds)));
    }
    return nextTime - elapsedSeconds;
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const status = uploadResult?.status;
  const failed = status === 'error' || status === 'not_found' || (!!error && !!uploadResult);
  const completed = status === 'completed';
  const reachedIndex = STAGES.reduce((last, [, at], index) => (peakProgress >= at ? index : last), 0);
  const stageState = index => {
    if (completed) return 'done';
    if (index < reachedIndex) return 'done';
    if (index === reachedIndex) return failed ? 'error' : 'active';
    return 'pending';
  };
  const remaining = uploading && progress > 10 && progress < 100 ? getEstimatedTimeRemaining(progress, elapsedTime) : null;
  const heading = completed ? 'Processing complete.' : status === 'not_found' ? 'Contract not found.'
    : failed ? 'Processing failed.' : 'Processing your contract…';

  return (
    <div className="page">
      <PageHeader
        index="02"
        eyebrow="Upload"
        title="Add a contract to the graph."
        description="Drop a PDF. LexiGuard parses it, extracts parties and clauses, and links it into the knowledge graph. Most contracts take two to five minutes."
      />

      <section className="container-x grid gap-6 pb-24 pt-8 lg:grid-cols-[1.4fr_1fr]">
        <Reveal self y={40}>
          <input type="file" accept=".pdf" onChange={handleFileChange} className="sr-only" id="file-upload" disabled={uploading} />
          <label
            htmlFor="file-upload"
            className={`dropzone ${dragActive ? 'is-drag' : ''} ${uploading ? 'is-disabled' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            data-cursor-text={uploading ? undefined : 'Choose a PDF'}
          >
            <span className="dropzone__icon" aria-hidden="true">
              {file ? <FileText size={22} /> : <ArrowUp size={22} />}
            </span>
            <span className="display-m max-w-[16ch] break-words">
              {file ? file.name : dragActive ? 'Release to add it.' : 'Drop a PDF here, or click to browse.'}
            </span>
            <span className="text-[0.95rem] opacity-70">
              {file ? formatFileSize(file.size) : 'PDF files only, up to 10 MB'}
            </span>
          </label>

          {error && !uploadResult && (
            <div className="notice mt-4" role="alert">
              <AlertCircle size={18} className="mt-0.5 flex-none" aria-hidden="true" /> {error}
            </div>
          )}

          {file && !uploadResult && (
            <div className="mt-4 flex flex-wrap gap-3">
              <Button onClick={handleUpload} disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload and process'}
              </Button>
              <Button variant="outline" icon={RotateCcw} onClick={reset} disabled={uploading}>Choose another</Button>
            </div>
          )}
        </Reveal>

        <Reveal self y={40} delay={0.1}>
          <div className="panel h-full p-6">
            {uploadResult ? (
              <div aria-live="polite">
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-[2rem] leading-[1.15]">{heading}</h2>
                  {completed ? <CheckCircle className="flex-none text-[var(--color-mint)]" size={26} aria-hidden="true" />
                    : failed ? <AlertCircle className="flex-none text-[#ff8a7a]" size={26} aria-hidden="true" /> : null}
                </div>

                <div className="mt-6 flex items-baseline justify-between gap-4 text-sm">
                  <span className="text-[var(--muted)]">{failed && error ? error : currentStep}</span>
                  <span className="tabular flex-none font-medium">
                    {elapsedTime > 0 && formatTime(elapsedTime)}
                    {remaining > 0 && <span className="text-[var(--muted)]"> · ~{formatTime(remaining)} left</span>}
                    <span className="ml-3">{progress}%</span>
                  </span>
                </div>
                <div className="progress mt-3" aria-hidden="true"><span style={{ transform: `scaleX(${progress / 100})` }} /></div>

                <ol className="pipeline mt-6">
                  {STAGES.map(([label], index) => (
                    <li key={label} data-state={stageState(index)}>
                      <span className="pipeline__dot" aria-hidden="true" />
                      <span>{label}</span>
                      <span className="text-xs">
                        {stageState(index) === 'done' ? 'Done' : stageState(index) === 'active' ? 'Working' : stageState(index) === 'error' ? 'Stopped' : ''}
                      </span>
                    </li>
                  ))}
                </ol>

                <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
                  <div className="col-span-2">
                    <dt className="text-xs text-[var(--muted)]">Contract ID</dt>
                    <dd className="mono m-0 mt-1 break-all">{uploadResult.contract_id}</dd>
                  </div>
                  {uploadResult.size_bytes && (
                    <div>
                      <dt className="text-xs text-[var(--muted)]">File size</dt>
                      <dd className="m-0 mt-1">{formatFileSize(uploadResult.size_bytes)}</dd>
                    </div>
                  )}
                  <div>
                    <dt className="text-xs text-[var(--muted)]">Status</dt>
                    <dd className="m-0 mt-1 font-medium">{status ? status.replace('_', ' ') : 'unknown'}</dd>
                  </div>
                </dl>

                {completed && (
                  <div className="mt-6 flex flex-wrap gap-3">
                    <Button to={`/contract/${encodeURIComponent(uploadResult.graph_id || uploadResult.contract_id)}`}>View knowledge graph</Button>
                    <Button to="/query" variant="outline">Ask questions</Button>
                  </div>
                )}
                {failed && !uploading && (
                  <div className="mt-6">
                    <Button variant="outline" icon={RotateCcw} onClick={reset}>Try again</Button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full flex-col justify-between gap-8">
                <div>
                  <span className="eyebrow">What happens next</span>
                  <ol className="pipeline mt-6">
                    {STAGES.map(([label]) => (
                      <li key={label} data-state="pending">
                        <span className="pipeline__dot" aria-hidden="true" />
                        <span>{label}</span>
                        <span />
                      </li>
                    ))}
                  </ol>
                </div>
                <p className="text-body">
                  You can leave this page while it runs. The contract appears on the Dashboard once the graph is built.
                  {' '}<Link to="/" className="text-link text-[var(--fg)]">Open the Dashboard</Link>
                </p>
              </div>
            )}
          </div>
        </Reveal>
      </section>

      <section className="container-x pb-24">
        <Reveal className="process-cols">
          {[
            ['01', 'Upload a PDF', 'Any contract in PDF format, up to 10 MB.'],
            ['02', 'AI processing', 'Parties, clauses and relationships are extracted. Usually 2 to 5 minutes.'],
            ['03', 'Query and analyse', 'Ask questions and get answers with the clauses cited.'],
          ].map(([num, title, text]) => (
            <div key={num}>
              <span className="text-sm text-[var(--muted)]">{num}</span>
              <h3 className="mb-3 mt-8 text-[2rem] leading-[1.15]">{title}</h3>
              <p className="text-body">{text}</p>
            </div>
          ))}
        </Reveal>
      </section>
    </div>
  );
}
