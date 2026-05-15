// DOM Elements
const convertBtn = document.getElementById('convertBtn');
const downloadBtn = document.getElementById('downloadBtn');
const copyBtn = document.getElementById('copyBtn');
const preview = document.getElementById('preview');
const status = document.getElementById('status');

// State
let currentMarkdown = '';
let currentTitle = 'webpage';

// Initialize libraries
let turndownService;
let readabilityAvailable = false;

// Check if libraries are loaded
try {
    if (typeof TurndownService === 'undefined') {
        console.error('TurndownService is not loaded! Check script tags in sidepanel.html');
        showStatus('Error: System libraries missing (Turndown)', 'error');
    } else {
        turndownService = new TurndownService({
            headingStyle: 'atx',
            codeBlockStyle: 'fenced',
            bulletListMarker: '-'
        });
        console.log('TurndownService initialized.');
    }

    if (typeof Readability === 'undefined') {
        console.error('Readability is not loaded! Check script tags in sidepanel.html');
        showStatus('Error: System libraries missing (Readability)', 'error');
    } else {
        readabilityAvailable = true;
        console.log('Readability initialized.');
    }
} catch (e) {
    console.error('Library initialization error:', e);
    showStatus('Error initializing system: ' + e.message, 'error');
}

// Helpers
function showStatus(message, type = 'info') {
    if (!status) return;
    status.textContent = message;
    status.className = 'status-bar ' + (type === 'error' ? 'error' : '');

    // If it's empty, hide it
    if (!message) {
        status.classList.add('hidden');
    } else {
        status.classList.remove('hidden');
    }

    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            status.textContent = '';
            status.classList.add('hidden');
        }, 3000);
    }
}

function sanitizeFilename(title) {
    if (!title) return 'webpage';
    return title.replace(/[^a-z0-9]/gi, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').toLowerCase().substring(0, 100) || 'webpage';
}

// Main logic
async function convertPage() {
    if (!convertBtn) return;
    console.log('Convert initiated.');

    // Reset state
    convertBtn.disabled = true;
    convertBtn.textContent = 'Converting...';
    showStatus('Reading page...', 'info');
    preview.value = '';
    currentMarkdown = '';

    try {
        // 1. Get Active Tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab?.id) throw new Error('No active tab found.');

        // 2. Execute Script to get HTML
        console.log('Executing script on tab:', tab.id);
        const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
                return {
                    html: document.documentElement.outerHTML,
                    title: document.title,
                    url: window.location.href
                };
            }
        });

        if (!results?.[0]?.result) {
            throw new Error('Could not access page content. Try reloading the page.');
        }

        const { html, title, url } = results[0].result;
        currentTitle = title || 'webpage';

        // 3. Parse with Readability
        console.log('Parsing HTML...');
        const doc = new DOMParser().parseFromString(html, 'text/html');

        // Base URI fix for relative links
        if (url) {
            const base = doc.createElement('base');
            base.href = url;
            doc.head.appendChild(base);
        }

        let contentToConvert = '';
        let articleTitle = title;
        let byline = '';

        if (readabilityAvailable) {
            try {
                // Check if Readability constructor exists
                if (typeof Readability === 'function') {
                    var reader = new Readability(doc);
                    var article = reader.parse();

                    if (article && article.content) {
                        contentToConvert = article.content;
                        articleTitle = article.title || title;
                        byline = article.byline ? `\n> By ${article.byline}\n` : '';
                    } else {
                        console.warn('Readability returned null/empty, falling back to body.');
                        contentToConvert = doc.body.innerHTML;
                    }
                } else {
                    console.error('Readability is not a function/class');
                    contentToConvert = doc.body.innerHTML;
                }
            } catch (rErr) {
                console.error('Readability error:', rErr);
                contentToConvert = doc.body.innerHTML;
            }
        } else {
            contentToConvert = doc.body.innerHTML;
        }

        // 4. Convert to Markdown
        console.log('Converting to Markdown...');
        let markdown = turndownService.turndown(contentToConvert);

        // Post-processing
        const header = `# ${articleTitle}\n\n${byline ? byline + '\n' : ''}`;
        const metadata = `\n\n---\nCreated from: ${url}\n`;

        currentMarkdown = header + markdown + metadata;
        preview.value = currentMarkdown;

        // Update UI
        downloadBtn.disabled = false;
        copyBtn.disabled = false;
        showStatus('Converted!', 'success');

    } catch (err) {
        console.error('Conversion Failed:', err);
        showStatus('Failed: ' + err.message, 'error');
        preview.value = `Error: ${err.message}\n\nPlease check the console for details.`;
    } finally {
        convertBtn.disabled = false;
        convertBtn.textContent = 'Convert Page';
    }
}


// Event Listeners
if (convertBtn) convertBtn.addEventListener('click', convertPage);

if (downloadBtn) downloadBtn.addEventListener('click', () => {
    if (!currentMarkdown) return;
    const blob = new Blob([currentMarkdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = sanitizeFilename(currentTitle) + '.md';
    a.click();
    URL.revokeObjectURL(url);
});

if (copyBtn) copyBtn.addEventListener('click', async () => {
    if (!currentMarkdown) return;
    try {
        await navigator.clipboard.writeText(currentMarkdown);
        showStatus('Copied!', 'success');
    } catch (err) {
        showStatus('Copy failed', 'error');
    }
});

// Reset panel when user switches tabs
chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'TAB_SWITCHED') {
        currentMarkdown = '';
        currentTitle = 'webpage';
        if (preview) preview.value = '';
        if (downloadBtn) downloadBtn.disabled = true;
        if (copyBtn) copyBtn.disabled = true;
        if (status) { status.textContent = ''; status.classList.add('hidden'); }
    }
});
