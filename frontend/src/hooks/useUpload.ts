import { useCallback, useState } from "react";
import URLS from "../config/urls";
import { uploadFile, UploadResponse, ApiError } from "../utils/network";

export interface UploadSuccess {
  response: UploadResponse;
  file: File;
}

export interface UploadFailure {
  error: string;
  status: number;
  file: File;
}

interface UseUploadOptions {
  onSuccess?: (result: UploadSuccess) => void;
  onError?: (failure: UploadFailure) => void;
}

export function useUpload({ onSuccess, onError }: UseUploadOptions = {}) {
  const [uploading, setUploading] = useState(false);

  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const response = await uploadFile(URLS.upload, file);
        onSuccess?.({ response, file });
        return response;
      } catch (e) {
        const status = e instanceof ApiError ? e.status : 0;
        const error = e instanceof ApiError ? e.message : "Upload failed. Please try again.";
        onError?.({ error, status, file });
        return null;
      } finally {
        setUploading(false);
      }
    },
    [onSuccess, onError],
  );

  return { upload, uploading };
}

export default useUpload;
