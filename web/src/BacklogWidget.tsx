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
    // allow other props
    [key: string]: any;
}

const BacklogWidget = () => {
    const [items, setItems] = useState<BacklogItem[]>([]);

    useEffect(() => {
        // 1. Try to get data from structuredContent (Apps SDK native)
        let toolOutput = window.window.openai?.toolOutput?.structuredContent;

        // 2. Fallback: Parse from standard MCP text content
        if (!toolOutput) {
            const content = window.window.openai?.toolOutput?.content;
            if (Array.isArray(content) && content.length > 0 && content[0].text) {
                try {
                    toolOutput = JSON.parse(content[0].text);
                } catch (e) {
                    console.error("Failed to parse output JSON", e);
                }
            }
        }

        if (toolOutput) {
            const parsedItems: BacklogItem[] = [];

            // If it's the root object with categories
            // Iterate over keys: active_issues, experiments, protocols, monitoring, etc.
            const categories = ['active_issues', 'experiments', 'protocols', 'monitoring'];

            // Check if toolOutput has these categories
            let hasCategory = false;
            categories.forEach(cat => {
                if (toolOutput[cat]) hasCategory = true;
            });

            if (hasCategory) {
                categories.forEach(cat => {
                    if (toolOutput[cat] && typeof toolOutput[cat] === 'object') {
                        const categoryItems = toolOutput[cat];
                        Object.keys(categoryItems).forEach(key => {
                            const item = categoryItems[key];
                            if (item && typeof item === 'object') {
                                parsedItems.push({
                                    title: item.name || key,
                                    status: cat, // Use category as status for now
                                    context: item.description || '',
                                    ...item
                                });
                            }
                        });
                    }
                });
            }

            // Provide standard items check AFTER category check to merge? 
            // Or if parsedItems is filled, use it.

            // Fallback: if it WAS an array (legacy support) or just a direct list
            if (parsedItems.length === 0) {
                if (Array.isArray(toolOutput)) {
                    setItems(toolOutput);
                    return;
                } else if (toolOutput.backlog && Array.isArray(toolOutput.backlog)) {
                    setItems(toolOutput.backlog);
                    return;
                }
            }

            setItems(parsedItems);
        } else {
            console.log("No tool output found for BacklogWidget.");
            setItems([]);
        }
    }, []);

    if (items.length === 0) {
        return (
            <div style={{ padding: 20 }}>
                <h3>No backlog items found.</h3>
                <details>
                    <summary>Debug Info</summary>
                    <pre style={{ fontSize: '10px', overflow: 'auto', maxHeight: '300px' }}>
                        {JSON.stringify(window.window.openai?.toolOutput, null, 2)}
                    </pre>
                </details>
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
                </div>
            ))}
        </div>
    );
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
