import React, { useState } from 'react';

// Simple SVG Icons
const CodeIcon = () => (
  <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
  </svg>
);

const LoaderIcon = () => (
  <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);

const CheckIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const AlertIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const SmallCodeIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
  </svg>
);

export default function TestAutomationGenerator() {
  const [formData, setFormData] = useState({
    url: '',
    html: '',
    testCase: '',
    testData: '',
    testSteps: '',
    selectedLanguage: 'Java',
    selectedTool: 'Selenium'
  });
  
  const [status, setStatus] = useState('idle'); // idle, loading, success, error
  const [generatedCode, setGeneratedCode] = useState('');
  const [extractedXpaths, setExtractedXpaths] = useState([]);
  const [error, setError] = useState('');

  const handleInputChange = (e) => {
    const target = (e && e.target) ? e.target : e;
    const { name, value } = target || {};
    if (!name) return;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  // REPLACE 'localhost' with your computer's IP address (e.g., '192.168.1.15') if testing from another device
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

  const generateCode = async () => {
    setStatus('loading');
    setError('');
    setGeneratedCode('');
    setExtractedXpaths([]);

    try {
      const res = await fetch(`${BACKEND_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server error: ${res.status} ${text}`);
      }

      const data = await res.json();

      // Backend should return { generated_code: string, extracted_xpaths: [...] }
      const code = data.generated_code || data.result || data.result_text || JSON.stringify(data);
      setGeneratedCode(code);

      const xpaths = data.extracted_xpaths || data.extractedXpaths || data.xpaths || data.extracted || [];
      if (Array.isArray(xpaths) && xpaths.length) setExtractedXpaths(xpaths);

      setStatus('success');
    } catch (err) {
      setError(err.message || 'Failed to generate code');
      setStatus('error');
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(generatedCode);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <CodeIcon />
            <h1 className="text-4xl font-bold text-white">Test Automation Generator</h1>
          </div>
          <p className="text-slate-300">Generate Selenium/Playwright test code from natural language</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input Form */}
          <div className="bg-white/10 backdrop-blur-lg rounded-lg p-6 border border-white/20">
            <h2 className="text-xl font-semibold text-white mb-4">Configuration</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Language
                </label>
                <select
                  name="selectedLanguage"
                  value={formData.selectedLanguage}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="Java">Java</option>
                  <option value="Python">Python</option>
                  <option value="JavaScript">JavaScript</option>
                  <option value="C#">C#</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Tool
                </label>
                <select
                  name="selectedTool"
                  value={formData.selectedTool}
                  onChange={handleInputChange}
                  className="w-full px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="Selenium">Selenium</option>
                  <option value="Playwright">Playwright</option>
                  <option value="Cypress">Cypress</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  URL or HTML
                </label>
                <input
                  type="text"
                  name="url"
                  value={formData.url}
                  onChange={handleInputChange}
                  placeholder="https://example.com or paste HTML"
                  className="w-full px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Test Case Name
                </label>
                <input
                  type="text"
                  name="testCase"
                  value={formData.testCase}
                  onChange={handleInputChange}
                  placeholder="Login Test"
                  className="w-full px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Test Steps
                </label>
                <textarea
                  name="testSteps"
                  value={formData.testSteps}
                  onChange={handleInputChange}
                  placeholder="1. Navigate to login page&#10;2. Enter username&#10;3. Enter password&#10;4. Click login button&#10;5. Verify successful login"
                  rows="5"
                  className="w-full px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200 mb-2">
                  Test Data (Optional)
                </label>
                <textarea
                  name="testData"
                  value={formData.testData}
                  onChange={handleInputChange}
                  placeholder="username: testuser&#10;password: Test123!"
                  rows="3"
                  className="w-full px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                />
              </div>

              <button
                onClick={generateCode}
                disabled={status === 'loading'}
                className="w-full px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {status === 'loading' ? (
                  <>
                    <LoaderIcon />
                    Generating...
                  </>
                ) : (
                  <>
                    <SmallCodeIcon />
                    Generate Code
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Output Section */}
          <div className="space-y-6">
            {/* Status Messages */}
            {status === 'success' && (
              <div className="bg-green-500/20 border border-green-500/50 rounded-lg p-4 flex items-center gap-3">
                <CheckIcon />
                <span className="text-green-200">Code generated successfully!</span>
              </div>
            )}

            {status === 'error' && (
              <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-4 flex items-center gap-3">
                <AlertIcon />
                <span className="text-red-200">{error}</span>
              </div>
            )}

            {/* Extracted Elements */}
            {extractedXpaths.length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-lg p-6 border border-white/20">
                <h3 className="text-lg font-semibold text-white mb-3">
                  Extracted Elements ({extractedXpaths.length})
                </h3>
                <div className="max-h-48 overflow-y-auto space-y-2">
                  {extractedXpaths.map((el, idx) => (
                    <div key={idx} className="text-sm bg-slate-800/50 rounded p-2">
                      <span className="text-purple-300 font-mono">{el.variable_name}</span>
                      <span className="text-slate-400 mx-2">→</span>
                      <span className="text-slate-300">{el.xpath}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Generated Code */}
            {generatedCode && (
              <div className="bg-white/10 backdrop-blur-lg rounded-lg border border-white/20 overflow-hidden">
                <div className="flex items-center justify-between p-4 border-b border-white/20">
                  <h3 className="text-lg font-semibold text-white">Generated Code</h3>
                  <button
                    onClick={copyToClipboard}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm rounded-lg transition-colors"
                  >
                    Copy Code
                  </button>
                </div>
                <pre className="p-6 overflow-x-auto max-h-96 overflow-y-auto text-left whitespace-pre-wrap break-words">
                  <code className="text-sm text-slate-200 font-mono">
                    {generatedCode}
                  </code>
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
