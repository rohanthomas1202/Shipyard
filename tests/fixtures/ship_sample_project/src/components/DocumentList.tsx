import React from 'react';
import { Document } from '../types/index.js';

interface Props {
  documents: Document[];
}

export function DocumentList({ documents }: Props) {
  return (
    <ul>
      {documents.map((doc) => (
        <li key={doc.id}>{doc.title}</li>
      ))}
    </ul>
  );
}
