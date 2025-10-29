/**
 * TabGraph Extension Configuration
 *
 * Edit this file to customize extension behavior.
 */

export const CONFIG = {
  // Backend server URL
  // Change this if running backend on different port or remote server
  BACKEND_URL: 'http://localhost:8000',

  // Tab monitoring interval in minutes
  MONITOR_INTERVAL_MINUTES: 5,

  // Similarity threshold for clustering (0.0 - 1.0)
  // Lower = more tabs grouped together (more general)
  // Higher = fewer tabs grouped together (more specific)
  // Note: Backend also has this setting - should match
  SIMILARITY_THRESHOLD: 0.70,
};
