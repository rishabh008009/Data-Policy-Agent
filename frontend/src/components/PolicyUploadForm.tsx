/**
 * Policy Upload Form Component
 * 
 * Provides drag-and-drop file upload functionality for PDF policy documents.
 * Handles file validation, upload progress, and success/error states.
 * 
 * Requirements: 1.1 - PDF Policy Document Ingestion
 */

import { useCallback, useState, useRef } from 'react';
import { uploadPolicy } from '../api';
import type { PolicyUploadResponse, ApiError } from '../api/types';

/**
 * Upload state enum for tracking component state
 */
type UploadState = 'idle' | 'dragging' | 'uploading' | 'success' | 'error';

/**
 * Format file size for display
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Validate that the file is a PDF
 */
function isValidPdfFile(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}

/**
 * Props for the PolicyUploadForm component
 */
interface PolicyUploadFormProps {
  /** Callback when upload succeeds */
  onUploadSuccess?: (policy: PolicyUploadResponse) => void;
  /** Callback when upload fails */
  onUploadError?: (error: string) => void;
  /** Maximum file size in bytes (default: 10MB) */
  maxFileSize?: number;
}

/**
 * Upload icon SVG component
 */
const UploadIcon = () => (
  <svg
    className="w-12 h-12 text-gray-400"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
    />
  </svg>
);

/**
 * Document icon SVG component
 */
const DocumentIcon = () => (
  <svg
    className="w-8 h-8 text-red-500"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
    />
  </svg>
);

/**
 * Success icon SVG component
 */
const SuccessIcon = () => (
  <svg
    className="w-12 h-12 text-green-500"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

/**
 * Error icon SVG component
 */
const ErrorIcon = () => (
  <svg
    className="w-12 h-12 text-red-500"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
    />
  </svg>
);

/**
 * Policy Upload Form Component
 * 
 * Features:
 * - Drag-and-drop file upload area
 * - Click to browse files option
 * - File type validation (PDF only)
 * - Upload progress indicator
 * - Success state with policy info
 * - Error state with retry option
 * - File size display
 */
export function PolicyUploadForm({
  onUploadSuccess,
  onUploadError,
  maxFileSize = 10 * 1024 * 1024, // 10MB default
}: PolicyUploadFormProps) {
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadedPolicy, setUploadedPolicy] = useState<PolicyUploadResponse | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  /**
   * Handle file selection and validation
   */
  const handleFileSelect = useCallback((file: File) => {
    // Reset previous state
    setErrorMessage(null);
    setUploadedPolicy(null);

    // Validate file type
    if (!isValidPdfFile(file)) {
      setErrorMessage('Please upload a PDF file. Only PDF documents are supported.');
      setUploadState('error');
      onUploadError?.('Invalid file type');
      return;
    }

    // Validate file size
    if (file.size > maxFileSize) {
      setErrorMessage(`File size exceeds the maximum limit of ${formatFileSize(maxFileSize)}.`);
      setUploadState('error');
      onUploadError?.('File too large');
      return;
    }

    setSelectedFile(file);
    setUploadState('idle');
  }, [maxFileSize, onUploadError]);

  /**
   * Handle drag over event
   */
  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (uploadState !== 'uploading') {
      setUploadState('dragging');
    }
  }, [uploadState]);

  /**
   * Handle drag leave event
   */
  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (uploadState !== 'uploading') {
      setUploadState('idle');
    }
  }, [uploadState]);

  /**
   * Handle file drop event
   */
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (uploadState === 'uploading') return;

    setUploadState('idle');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, [uploadState, handleFileSelect]);

  /**
   * Handle click to browse files
   */
  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Handle file input change
   */
  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
    // Reset input value to allow selecting the same file again
    e.target.value = '';
  }, [handleFileSelect]);

  /**
   * Handle file upload
   */
  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;

    setUploadState('uploading');
    setUploadProgress(0);
    setErrorMessage(null);

    // Simulate progress updates (since axios doesn't provide real progress for small files)
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return prev;
        }
        return prev + 10;
      });
    }, 200);

    try {
      const policy = await uploadPolicy(selectedFile);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      setUploadedPolicy(policy);
      setUploadState('success');
      onUploadSuccess?.(policy);
    } catch (err) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      
      const apiError = err as ApiError;
      const message = apiError.detail || 'Failed to upload policy. Please try again.';
      setErrorMessage(message);
      setUploadState('error');
      onUploadError?.(message);
    }
  }, [selectedFile, onUploadSuccess, onUploadError]);

  /**
   * Handle retry after error
   */
  const handleRetry = useCallback(() => {
    setUploadState('idle');
    setErrorMessage(null);
    setUploadProgress(0);
  }, []);

  /**
   * Handle reset to upload another file
   */
  const handleReset = useCallback(() => {
    setUploadState('idle');
    setSelectedFile(null);
    setUploadProgress(0);
    setErrorMessage(null);
    setUploadedPolicy(null);
  }, []);

  /**
   * Remove selected file
   */
  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null);
    setUploadState('idle');
    setErrorMessage(null);
  }, []);

  // Render success state
  if (uploadState === 'success' && uploadedPolicy) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="text-center">
          <SuccessIcon />
          <h3 className="mt-4 text-lg font-semibold text-gray-900">
            Policy Uploaded Successfully!
          </h3>
          <p className="mt-2 text-gray-600">
            {uploadedPolicy.filename}
          </p>
          
          {/* Policy Info */}
          <div className="mt-4 p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Policy ID:</span>
                <p className="font-medium text-gray-900 truncate">{uploadedPolicy.id}</p>
              </div>
              <div>
                <span className="text-gray-600">Rules Extracted:</span>
                <p className="font-medium text-gray-900">
                  {uploadedPolicy.rule_count} rules
                </p>
              </div>
            </div>
          </div>

          {uploadedPolicy.rule_count > 0 && (
            <p className="mt-4 text-sm text-green-600">
              {uploadedPolicy.message}
            </p>
          )}

          <button
            onClick={handleReset}
            className="mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Upload Another Policy
          </button>
        </div>
      </div>
    );
  }

  // Render error state
  if (uploadState === 'error' && errorMessage) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="text-center">
          <ErrorIcon />
          <h3 className="mt-4 text-lg font-semibold text-red-800">
            Upload Failed
          </h3>
          <p className="mt-2 text-red-600">
            {errorMessage}
          </p>
          
          {selectedFile && (
            <p className="mt-2 text-sm text-gray-500">
              File: {selectedFile.name} ({formatFileSize(selectedFile.size)})
            </p>
          )}

          <div className="mt-6 flex justify-center gap-4">
            <button
              onClick={handleRetry}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Choose Different File
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render uploading state
  if (uploadState === 'uploading') {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="text-center">
          {/* Spinning loader */}
          <div className="mx-auto w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
          
          <h3 className="mt-4 text-lg font-semibold text-gray-900">
            Uploading Policy...
          </h3>
          <p className="mt-2 text-gray-600">
            {selectedFile?.name}
          </p>

          {/* Progress bar */}
          <div className="mt-4 w-full bg-gray-200 rounded-full h-2.5">
            <div
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
          <p className="mt-2 text-sm text-gray-500">
            {uploadProgress}% complete
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Processing PDF and extracting compliance rules...
          </p>
        </div>
      </div>
    );
  }

  // Render idle/dragging state (default)
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileInputChange}
        className="hidden"
      />

      {/* Drag and drop area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleBrowseClick}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${uploadState === 'dragging'
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }
        `}
      >
        <UploadIcon />
        <h3 className="mt-4 text-lg font-semibold text-gray-900">
          {uploadState === 'dragging'
            ? 'Drop your PDF here'
            : 'Drag and drop your policy PDF'
          }
        </h3>
        <p className="mt-2 text-gray-600">
          or{' '}
          <span className="text-blue-600 hover:text-blue-700 font-medium">
            browse files
          </span>
        </p>
        <p className="mt-2 text-sm text-gray-500">
          PDF files only, up to {formatFileSize(maxFileSize)}
        </p>
      </div>

      {/* Selected file preview */}
      {selectedFile && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <DocumentIcon />
              <div>
                <p className="font-medium text-gray-900">{selectedFile.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleRemoveFile();
              }}
              className="p-1 text-gray-400 hover:text-red-500 transition-colors"
              title="Remove file"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          {/* Upload button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleUpload();
            }}
            className="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Upload Policy
          </button>
        </div>
      )}
    </div>
  );
}

export default PolicyUploadForm;
