export interface Document {
  id: string;
  title: string;
  content: string;
  document_type: 'wiki' | 'issue' | 'project';
  created_at: string;
  updated_at: string;
}

export interface ApiResponse<T> {
  data: T;
  error?: string;
}
