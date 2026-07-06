import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { Document } from "../components/Sidebar";

interface UserDocs {
  documents: Document[];
  activeDocId: string | null;
}

export interface DocumentsState {
  documents: Document[];
  activeDocId: string | null;
  userKey: string | null;
  byUser: Record<string, UserDocs>;
}

const initialState: DocumentsState = {
  documents: [],
  activeDocId: null,
  userKey: null,
  byUser: {},
};

const documentsSlice = createSlice({
  name: "documents",
  initialState,
  reducers: {
    addDocument(state, action: PayloadAction<Document>) {
      state.documents.push(action.payload);
      state.activeDocId = action.payload.id;
    },
    setActiveDoc(state, action: PayloadAction<string>) {
      state.activeDocId = action.payload;
    },
    removeDocument(state, action: PayloadAction<string>) {
      state.documents = state.documents.filter((d) => d.id !== action.payload);
      if (state.activeDocId === action.payload) {
        state.activeDocId = state.documents[0]?.id ?? null;
      }
    },
    resetDocuments(state) {
      state.documents = [];
      state.activeDocId = null;
      if (state.userKey) {
        state.byUser[state.userKey] = { documents: [], activeDocId: null };
      }
    },
    setUserScope(state, action: PayloadAction<string>) {
      const nextKey = action.payload;
      if (state.userKey === nextKey) return;

      if (state.userKey === null) {
        state.userKey = nextKey;
        state.byUser[nextKey] = {
          documents: state.documents,
          activeDocId: state.activeDocId,
        };
        return;
      }

      state.byUser[state.userKey] = {
        documents: state.documents,
        activeDocId: state.activeDocId,
      };
      const next = state.byUser[nextKey];
      state.documents = next?.documents ?? [];
      state.activeDocId = next?.activeDocId ?? null;
      state.userKey = nextKey;
    },
  },
});

export const {
  addDocument,
  setActiveDoc,
  removeDocument,
  resetDocuments,
  setUserScope,
} = documentsSlice.actions;
export default documentsSlice.reducer;
