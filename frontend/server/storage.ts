// Minimal storage - app is mostly stateless (Python backend handles persistence)
export interface IStorage {}

export class MemStorage implements IStorage {}

export const storage = new MemStorage();
