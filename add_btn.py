import re

def modify_dashboard():
    with open("frontend/src/components/Dashboard.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Add the export function
    export_fn = """
  const exportPlatformHighlights = async () => {
    try {
      let query = `?start_date=${startDate}&end_date=${endDate}`;
      const res = await axios.get(`${API_URL}/export-platform-highlights${query}`, { responseType: 'blob' });
      
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Platform_Highlights_${startDate}_${endDate}.pptx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error("Error exporting slides:", error);
      alert("Failed to export slides. See console.");
    }
  };
"""
    # Insert it right before "const exportCrossPlatform" (around line 654)
    # Search for "const exportCrossPlatform"
    if "const exportCrossPlatform" in content:
        content = content.replace("const exportCrossPlatform =", export_fn + "\n  const exportCrossPlatform =")
    
    # 2. Add the button in the UI
    # Search for "{activeTab === 'highlights' && ("
    target_ui = "{activeTab === 'highlights' && (\n        <div>\n          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>\n            <button\n              onClick={exportPlatformHighlights}\n              style={{\n                padding: '0.6rem 1.2rem',\n                backgroundColor: '#dc2626',\n                color: 'white',\n                border: 'none',\n                borderRadius: '8px',\n                cursor: 'pointer',\n                fontWeight: '600',\n                display: 'flex',\n                alignItems: 'center',\n                gap: '0.5rem',\n                boxShadow: '0 4px 6px -1px rgba(220, 38, 38, 0.3)',\n                transition: 'all 0.2s ease'\n              }}\n              onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}\n              onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}\n            >\n              <Download size={18} /> Export AI Slide (.pptx)\n            </button>\n          </div>\n          {platformStats"

    if "{activeTab === 'highlights' && (\n        <div>\n          {platformStats" in content:
        content = content.replace(
            "{activeTab === 'highlights' && (\n        <div>\n          {platformStats",
            target_ui
        )
    elif "{activeTab === 'highlights' && (" in content:
        # Fallback if whitespace differs
        content = re.sub(
            r"(\{activeTab === 'highlights' && \(\s*<div>\s*)\{platformStats",
            target_ui.replace("{activeTab === 'highlights' && (\n        <div>\n          <div", r"\1<div"),
            content
        )
        
    with open("frontend/src/components/Dashboard.jsx", "w", encoding="utf-8") as f:
        f.write(content)

modify_dashboard()
