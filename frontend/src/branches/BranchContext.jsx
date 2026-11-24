import { createContext, useContext } from 'react';

export const BranchContext = createContext({ branchId: null, branches: [], user: null });
export function useCurrentBranch() { return useContext(BranchContext); }
