export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Date;
}
export interface Document {
  id: string;
  title: string;
  content: string;
  authorId: string;
  createdAt: Date;
}
export interface ApiResponse<T> {
  data: T;
  error?: string;
}
