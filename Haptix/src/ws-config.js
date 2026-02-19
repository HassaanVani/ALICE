/**
 * Shared WebSocket configuration for Haptix.
 * All bridges import URLs from here to avoid hardcoding ports in every file.
 */

const WS_HOST = window.location.hostname || 'localhost';

export const TENSOR_WS_URL = `ws://${WS_HOST}:8765`;
export const PUPPET_WS_URL = `ws://${WS_HOST}:8766`;
