import React, { useEffect, useRef, useState } from "react";
import Sidebar, { Document, DocType } from "../components/Sidebar";
import ChatArea from "../components/ChatArea";
import ChatInput from "../components/ChatInput";
import RightPanel from "../components/RightPanel";
import TopBar from "../components/TopBar";
import Modal, { ModalVariant } from "../components/Modal";
import useChat from "../hooks/useChat";
import useUpload from "../hooks/useUpload";
import StringData from "../StringData";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import { addDocument, resetDocuments, setActiveDoc, setUserScope } from "../store/documentsSlice";
import { useAuth } from "../auth/AuthContext";
import { getUserDocKey } from "../auth/token";

const EXT_TO_TYPE: Record<string, DocType> = {
  pdf: "pdf",
  doc: "doc",
  docx: "doc",
  txt: "txt",
  md: "md",
};

interface ModalState {
  open: boolean;
  variant: ModalVariant;
  title: string;
  message: string;
  details?: string;
}

const CLOSED_MODAL: ModalState = {
  open: false,
  variant: "success",
  title: "",
  message: "",
};

function fmtSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

const ChatPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { username } = useAuth();
  const documents = useAppSelector((s) => s.documents.documents);
  const activeDocId = useAppSelector((s) => s.documents.activeDocId);

  useEffect(() => {
    if (username) dispatch(setUserScope(getUserDocKey(username)));
  }, [username, dispatch]);
  const [modal, setModal] = useState<ModalState>(CLOSED_MODAL);
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { messages, isThinking, pipelineSteps, sources, toolsUsed, evalScores, sendQuestion } =
    useChat();

  const closeModal = () => setModal((m) => ({ ...m, open: false }));

  const { upload, uploading } = useUpload({
    onSuccess: ({ response, file }) => {
      const ext = file.name.split(".").pop()?.toLowerCase() || "";
      const newDoc: Document = {
        id: `doc-${Date.now()}`,
        name: file.name,
        meta: `${fmtSize(file.size)} · indexed`,
        type: EXT_TO_TYPE[ext] || "txt",
        status: "ready",
      };
      dispatch(addDocument(newDoc));
      setModal({
        open: true,
        variant: "success",
        title: StringData.modal.uploadSuccessTitle,
        message: StringData.modal.uploadSuccessMessage
          .replace("{file}", file.name)
          .replace("{count}", String(response.documents_indexed)),
        details: response.message,
      });
    },
    onError: ({ error, file }) => {
      setModal({
        open: true,
        variant: "error",
        title: StringData.modal.uploadErrorTitle,
        message: StringData.modal.uploadErrorMessage.replace("{file}", file.name),
        details: error,
      });
    },
  });

  const handleUploadClick = () => fileInputRef.current?.click();

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload(file);
    e.target.value = "";
  };

  return (
    <div className="flex h-screen bg-ink text-txt-pri font-sans overflow-hidden">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.md,.docx"
        className="hidden"
        onChange={handleFileSelected}
      />

      {(leftOpen || rightOpen) && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          aria-hidden="true"
          onClick={() => {
            setLeftOpen(false);
            setRightOpen(false);
          }}
        />
      )}

      <div
        className={`fixed inset-y-0 left-0 z-40 flex transform transition-transform duration-300 ease-in-out lg:static lg:z-auto lg:translate-x-0 ${
          leftOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          documents={documents}
          activeDocId={activeDocId}
          evalScores={evalScores}
          isThinking={isThinking}
          uploading={uploading}
          onDocSelect={(id) => {
            dispatch(setActiveDoc(id));
            setLeftOpen(false);
          }}
          onUploadClick={handleUploadClick}
          onResetDocs={() => dispatch(resetDocuments())}
        />
      </div>

      <main className="flex-1 flex flex-col min-w-0">
        <TopBar
          onToggleLeft={() => setLeftOpen(true)}
          onToggleRight={() => setRightOpen(true)}
        />
        <ChatArea
          messages={messages}
          isThinking={isThinking}
          onCitationClick={() => {}}
          onSourceChipClick={() => {}}
          onSuggestionClick={sendQuestion}
        />
        <ChatInput
          docCount={documents.length}
          onSend={sendQuestion}
          disabled={isThinking}
        />
      </main>

      <div
        className={`fixed inset-y-0 right-0 z-40 flex transform transition-transform duration-300 ease-in-out lg:static lg:z-auto lg:translate-x-0 ${
          rightOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <RightPanel
          pipelineSteps={pipelineSteps}
          sources={sources}
          toolsUsed={toolsUsed}
          isThinking={isThinking}
        />
      </div>

      <Modal
        open={modal.open}
        variant={modal.variant}
        title={modal.title}
        message={modal.message}
        details={modal.details}
        onClose={closeModal}
        actions={
          modal.variant === "error"
            ? [
                { label: StringData.modal.closeBtn, onClick: closeModal, kind: "ghost" },
                {
                  label: StringData.modal.retryBtn,
                  onClick: () => {
                    closeModal();
                    handleUploadClick();
                  },
                  kind: "primary",
                },
              ]
            : undefined
        }
      />
    </div>
  );
};

export default ChatPage;
