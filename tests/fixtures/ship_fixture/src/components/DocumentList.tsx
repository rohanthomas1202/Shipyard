import React from 'react';
import { Document } from '../types';
interface Props { documents: Document[]; }
export function DocumentList({ documents }: Props) {
  return (
    <ul>{documents.map(d => <li key={d.id}>{d.title}</li>)}</ul>
  );
}
