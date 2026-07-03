import { TraceRecord } from './api';

export interface TreeNode extends TraceRecord {
  children: TreeNode[];
}

export function buildTraceTree(traces: TraceRecord[]): TreeNode[] {
  const map: { [id: string]: TreeNode } = {};
  const roots: TreeNode[] = [];
  
  traces.forEach(t => {
    map[t.id] = { ...t, children: [] };
  });
  
  traces.forEach(t => {
    const node = map[t.id];
    if (t.parent_trace_id && map[t.parent_trace_id]) {
      map[t.parent_trace_id].children.push(node);
    } else {
      roots.push(node);
    }
  });
  
  return roots;
}
