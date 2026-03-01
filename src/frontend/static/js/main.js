// Wait for the HTML to load
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const container = document.getElementById('moduleContainer');

    // 1. Fetch the data from your Python 'get_policies' route
    fetch('/api/policies')
        .then(response => response.json())
        .then(policies => {
            
            // 2. Listen for the user typing in the search bar
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                
                if (!query) {
                    container.innerHTML = '<p>Enter a keyword to discover relevant policies.</p>';
                    return;
                }

                // 3. RELEVANCE LOGIC: Filter and Sort
                const results = policies
                    .map(policy => {
                        let score = 0;
                        // Title matches are high priority (10 points)
                        if (policy.name.toLowerCase().includes(query)) score += 10;
                        // Description matches are secondary (5 points)
                        if ((policy.description_plain_english || '').toLowerCase().includes(query)) score += 5;
                        return { ...policy, score };
                    })
                    .filter(p => p.score > 0) // Only show things that match
                    .sort((a, b) => b.score - a.score); // Highest relevance first

                renderModules(results, container);
            });
        });
});

// Function to turn the data into clickable HTML modules
function renderModules(data, container) {
    container.innerHTML = data.map(policy => `
        <div class="module-card" onclick="showDetails(${JSON.stringify(policy).replace(/"/g, '&quot;')})">
            <h3>${policy.name}</h3>
            <p>${(policy.description_plain_english || '').substring(0, 100)}...</p>
            <span class="relevance-tag">Relevance: ${policy.score}</span>
        </div>
    `).join('');
}