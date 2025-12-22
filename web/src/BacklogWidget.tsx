import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

// Minimal type definition for window.openai
declare global {
    interface Window {
        openai?: {
            toolOutput?: {
                structuredContent?: {
                    backlog?: BacklogItem[];
                    // Handle case where backlog is the root array or inside a property
                    [key: string]: any;
                }
            }
        }
    }
}

interface BacklogItem {
    title: string;
    status?: string;
    context?: string;
    created_at?: string;
    // allow other props
    [key: string]: any;
}

const BacklogWidget = () => {
    const [items, setItems] = useState<BacklogItem[]>([]);
    const [statusText, setStatusText] = useState("Initializing...");

    const checkData = (attempt: number) => {
        // @ts-ignore
        const rawOutput = window.openai?.toolOutput;
        console.log(`[BacklogWidget] Checking attempt ${attempt}`, rawOutput);
        const result = parseToolOutput(rawOutput);

        if (result && result.length > 0) {
            console.log("BacklogWidget: Data found on attempt", attempt);
            setItems(result);
            return true; // Found
        }
        return false;
    };

    const runPolling = () => {
        let attempts = 0;
        const maxAttempts = 100; // Try for 10 seconds (100ms * 100)
        setStatusText("Waiting for data...");

        // Immediate check
        if (checkData(0)) return;

        // Poll
        const interval = setInterval(() => {
            attempts++;
            if (checkData(attempts) || attempts >= maxAttempts) {
                clearInterval(interval);
                if (attempts >= maxAttempts) {
                    console.log("BacklogWidget: No data found after polling.");
                    setStatusText("No data received from ChatGPT.");
                }
            }
        }, 100);

        return () => clearInterval(interval);
    };

    useEffect(() => {
        runPolling();
    }, []);

    if (items.length === 0) {
        return (
            <div style={{ padding: 20, textAlign: 'center' }}>
                <h3 style={{ marginBottom: '10px' }}>{statusText}</h3>
                <p style={{ fontSize: '12px', color: '#666', marginBottom: '20px' }}>
                    If this persists, please try reloading the page.
                </p>
                <button
                    onClick={() => runPolling()}
                    style={{
                        padding: '8px 16px',
                        background: '#10a37f',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                    }}
                >
                    Retry Fetching Data
                </button>
            </div>
        );
    }

    return (
        <div className="carousel">
            {items.map((item, idx) => (
                <div key={idx} className="card">
                    <h3>{item.title}</h3>
                    <div className={`status ${getNormalisedStatus(item.status)}`}>
                        {item.status || 'Unknown'}
                    </div>
                    {item.context && (
                        <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
                            {item.context}
                        </p>
                    )}
                    {item.created_at && (
                        <p style={{ fontSize: '10px', color: '#999', marginTop: '8px', textAlign: 'right' }}>
                            Created: {item.created_at}
                        </p>
                    )}
                </div>
            ))}
        </div>
    );
};

// Helper to clean JSON string from Markdown code blocks
const cleanJsonString = (text: string): string => {
    const jsonMatch = text.match(/```json\n([\s\S]*?)\n```/) || text.match(/```\n([\s\S]*?)\n```/);
    if (jsonMatch) {
        return jsonMatch[1];
    }
    return text;
};

// Pure function to parse tool output
const parseToolOutput = (rawOutput: any): BacklogItem[] | null => {
    let toolOutput: any = null;

    // 1. Try native structuredContent
    if (rawOutput?.structuredContent) {
        toolOutput = rawOutput.structuredContent;
    }
    // 2. Try raw string
    else if (typeof rawOutput === 'string') {
        try {
            toolOutput = JSON.parse(cleanJsonString(rawOutput));
        } catch (e) {
            console.error("Failed to parse toolOutput string", e);
        }
    }
    // 3. Try standard TextContent array
    else if (rawOutput?.content && Array.isArray(rawOutput.content)) {
        const content = rawOutput.content;
        if (content.length > 0 && content[0].text) {
            try {
                toolOutput = JSON.parse(cleanJsonString(content[0].text));
            } catch (e) {
                console.error("Failed to parse output content JSON", e);
            }
        }
    }
    // 4. Try direct text property
    else if (rawOutput?.text && typeof rawOutput.text === 'string') {
        try {
            toolOutput = JSON.parse(cleanJsonString(rawOutput.text));
        } catch (e) {
            console.error("Failed to parse output.text", e);
        }
    }

    if (!toolOutput) return null;

    // Parse items from the resolved object
    const parsedItems: BacklogItem[] = [];
    const categories = ['active_issues', 'experiments', 'protocols', 'monitoring'];

    // Check categories
    categories.forEach(cat => {
        if (toolOutput[cat] && typeof toolOutput[cat] === 'object') {
            const categoryItems = toolOutput[cat];
            Object.keys(categoryItems).forEach(key => {
                const item = categoryItems[key];
                if (item && typeof item === 'object') {
                    parsedItems.push({
                        title: item.name || key,
                        status: cat,
                        context: item.description || '',
                        ...item
                    });
                }
            });
        }
    });

    // If categories found, return them
    if (parsedItems.length > 0) return parsedItems;

    // Fallback: legacy array or direct 'backlog' property
    if (Array.isArray(toolOutput)) {
        return toolOutput;
    } else if (toolOutput.backlog && Array.isArray(toolOutput.backlog)) {
        return toolOutput.backlog;
    }

    return null;
};

// Helper for style classes
const getNormalisedStatus = (status: string | undefined) => {
    const s = (status || '').toLowerCase();
    if (s.includes('active_issues')) return 'todo'; // Red/Warning
    if (s.includes('experiments')) return 'doing';  // Yellow/Action
    if (s.includes('protocols')) return 'done';     // Green/Stable
    if (s.includes('monitoring')) return 'doing';   // Yellow/Watch

    // Legacy fallbacks
    if (s.includes('done') || s.includes('complete')) return 'done';
    if (s.includes('doing') || s.includes('progress')) return 'doing';
    return 'todo';
}

// Render
const container = document.getElementById('backlog-root');
if (container) {
    const root = createRoot(container);
    root.render(<BacklogWidget />);
}
