/**
 * TabGraph Content Script
 *
 * Injected into all pages to extract content when tab is marked as important.
 */

// ============================================================================
// Message Handler
// ============================================================================

/**
 * Listen for messages from background script.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract-content') {
    try {
      const content = extractPageContent();
      sendResponse({ success: true, content });
    } catch (error) {
      console.error('Error extracting content:', error);
      sendResponse({ success: false, error: error.message });
    }
    return true;
  }
});

// ============================================================================
// Content Extraction
// ============================================================================

/**
 * Extract meaningful content from the current page.
 *
 * @returns {Object} Extracted content data
 */
function extractPageContent() {
  // Get page metadata
  const url = window.location.href;
  const title = document.title;

  // Extract main content (first 10k characters)
  const bodyText = document.body.innerText || document.body.textContent || '';
  const content = bodyText.substring(0, 10000);

  // Extract meta description if available
  const metaDescription = document.querySelector('meta[name="description"]');
  const description = metaDescription ? metaDescription.getAttribute('content') : '';

  // Extract keywords if available
  const metaKeywords = document.querySelector('meta[name="keywords"]');
  const keywords = metaKeywords ? metaKeywords.getAttribute('content') : '';

  // Extract main headings
  const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
    .map(h => h.innerText.trim())
    .filter(text => text.length > 0)
    .slice(0, 10);

  return {
    url,
    title,
    content,
    description,
    keywords,
    headings,
    timestamp: new Date().toISOString(),
  };
}

console.log('TabGraph content script loaded');
