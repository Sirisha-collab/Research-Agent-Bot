import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './ResearchAssistantUI.css';

const API_BASE_URL = 'http://127.0.0.1:8000';

// Utility function for API calls
const apiCall = async (endpoint, method = 'GET', data = null, isFile = false) => {
  try {
    const config = {
      method,
      url: `${API_BASE_URL}${endpoint}`,
      headers: isFile ? {} : { 'Content-Type': 'application/json' }
    };

    if (data) config.data = data;

    const response = await axios(config);
    return response.data;
  } catch (error) {
    throw error.response?.data || error.message;
  }
};

const ResearchAssistantUI = () => {
  // State management
  const [activeTab, setActiveTab] = useState('dashboard');
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Query state
  const [query, setQuery] = useState('');
  const [queryResults, setQueryResults] = useState(null);

  // Summary state
  const [summaryText, setSummaryText] = useState('');
  const [summaries, setSummaries] = useState({});
  const [selectedExpertiseLevel, setSelectedExpertiseLevel] = useState('intermediate');

  // Questions state
  const [questionsText, setQuestionsText] = useState('');
  const [questions, setQuestions] = useState({});
  const [numQuestions, setNumQuestions] = useState(5);
  const [pdfFile, setPdfFile] = useState(null);

  // Metrics state
  const [indexStats, setIndexStats] = useState(null);
  const [relevantDocIds, setRelevantDocIds] = useState('');
  const [evaluationResults, setEvaluationResults] = useState(null);

  // Auto-summaries state
  const [lastUploadSummaries, setLastUploadSummaries] = useState(null);

  // Initialize
  useEffect(() => {
    loadDocuments();
  }, []);

  // Load documents
  const loadDocuments = async () => {
    try {
      setLoading(true);
      const data = await apiCall('/documents');
      setDocuments(data.documents || []);

      // Also load index stats
      const stats = await apiCall('/index/stats');
      setIndexStats(stats.stats);
    } catch (err) {
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  // Handle file upload
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      setLoading(true);
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API_BASE_URL}/documents/upload`, formData);
      setSuccess(`Document uploaded: ${response.data.message}`);

      // Capture auto-generated summaries
      if (response.data.auto_summaries && response.data.auto_summaries.summaries) {
        setLastUploadSummaries({
          filename: response.data.filename,
          summaries: response.data.auto_summaries.summaries,
          timestamp: new Date().toLocaleTimeString()
        });
      }

      await loadDocuments();
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
      setLastUploadSummaries(null);
    } finally {
      setLoading(false);
    }
  };

  // Handle query
  const handleQuery = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      setError('Please enter a query');
      return;
    }

    try {
      setLoading(true);
      const data = await apiCall('/query', 'POST', {
        query,
        include_summary: true,
        expertise_level: selectedExpertiseLevel
      });
      setQueryResults(data);
      setError(null);
    } catch (err) {
      setError('Query failed');
    } finally {
      setLoading(false);
    }
  };

  // Handle summary generation
  const handleGenerateSummary = async (e) => {
    e.preventDefault();
    if (!summaryText.trim()) {
      setError('Please enter text to summarize');
      return;
    }

    try {
      setLoading(true);
      const data = await apiCall('/summaries/multi-level', 'POST', {
        text: summaryText
      });
      setSummaries(data.summaries || {});
      setError(null);
    } catch (err) {
      setError('Summary generation failed');
    } finally {
      setLoading(false);
    }
  };

  // Handle questions generation
  const handleGenerateQuestions = async (e) => {
    e.preventDefault();

    try {
      setLoading(true);

      const data = await apiCall('/questions/generate', 'POST', {
        pdf_path: "uploads/testing.pdf",
        num_questions: numQuestions
      });

      setQuestions(data.questions || {});
      setError(null);

    } catch (err) {
      setError('Question generation failed');
    } finally {
      setLoading(false);
    }
  };

  // Handle evaluation
  const handleEvaluate = async (e) => {
    e.preventDefault();
    if (!relevantDocIds.trim()) {
      setError('Please enter document IDs');
      return;
    }

    try {
      setLoading(true);
      const docIds = relevantDocIds.split(',').map(id => parseInt(id.trim()));
      const data = await apiCall('/evaluate/retrieval', 'POST', {
        relevant_doc_ids: docIds
      });
      setEvaluationResults(data.metrics);
      setError(null);
    } catch (err) {
      setError('Evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  // Clear all documents
  const handleClearAll = async () => {
    if (window.confirm('Are you sure you want to clear all documents?')) {
      try {
        setLoading(true);
        await apiCall('/documents/clear', 'DELETE');
        setSuccess('All documents cleared');
        await loadDocuments();
      } catch (err) {
        setError('Clear failed');
      } finally {
        setLoading(false);
      }
    }
  };

  // Dashboard Tab
  const DashboardTab = () => (
    <div className="tab-content">
      <h2>Dashboard</h2>

      <div className="stats-grid">
        {indexStats && (
          <>
            <div className="stat-card">
              <h3>Documents</h3>
              <p className="stat-value">{indexStats.num_documents}</p>
            </div>
            <div className="stat-card">
              <h3>Dimension</h3>
              <p className="stat-value">{indexStats.dimension}</p>
            </div>
            <div className="stat-card">
              <h3>Total Size</h3>
              <p className="stat-value">{indexStats.total_size_mb?.toFixed(2) || 0} MB</p>
            </div>
            <div className="stat-card">
              <h3>Index Type</h3>
              <p className="stat-value">{indexStats.index_type}</p>
            </div>
          </>
        )}
      </div>

      <div className="documents-section">
        <h3>Documents</h3>
        {documents.length > 0 ? (
          <table className="documents-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Pages</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc, idx) => (
                <tr key={idx}>
                  <td>{doc.filename}</td>
                  <td>{doc.num_pages}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No documents uploaded yet</p>
        )}
      </div>
    </div>
  );

  // Query Tab
  const QueryTab = () => (
    <div className="tab-content">
      <h2>Query Assistant</h2>

      <form onSubmit={handleQuery} className="form">
        <div className="form-group">
          <label>Query:</label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your research question..."
            rows="4"
          />
        </div>

        <div className="form-group">
          <label>Expertise Level:</label>
          <select value={selectedExpertiseLevel} onChange={(e) => setSelectedExpertiseLevel(e.target.value)}>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="expert">Expert</option>
          </select>
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Processing...' : 'Query'}
        </button>
      </form>

      {queryResults && (
        <div className="results-section">
          <h3>Results</h3>
          <div className="query-response">
            <h4>Response:</h4>
            <p>{queryResults.response}</p>
          </div>

          {queryResults.summary && (
            <div className="query-summary">
              <h4>Summary ({queryResults.expertise_level}):</h4>
              <p>{queryResults.summary}</p>
            </div>
          )}

          {queryResults.results && queryResults.results.length > 0 && (
            <div className="retrieved-docs">
              <h4>Retrieved Documents ({queryResults.retrieved_count}):</h4>
              {queryResults.results.map((result, idx) => (
                <div key={idx} className="retrieved-item">
                  <p><strong>Similarity:</strong> {(result.similarity * 100).toFixed(2)}%</p>
                  <p className="doc-text">{result.text.substring(0, 200)}...</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );

  // Summary Tab
  const SummaryTab = () => (
    <div className="tab-content">
      <h2>Summary Generation</h2>

      <form onSubmit={handleGenerateSummary} className="form">
        <div className="form-group">
          <label>Text to Summarize:</label>
          <textarea
            value={summaryText}
            onChange={(e) => setSummaryText(e.target.value)}
            placeholder="Paste the text you want to summarize..."
            rows="6"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Generating...' : 'Generate Summaries'}
        </button>
      </form>

      {Object.keys(summaries).length > 0 && (
        <div className="results-section">
          <h3>Summaries</h3>
          <div className="summaries-grid">
            {Object.entries(summaries).map(([level, data]) => (
              <div key={level} className="summary-card">
                <h4>{level.charAt(0).toUpperCase() + level.slice(1)}</h4>
                <div className="summary-content">
                  <p>{data.summary}</p>
                </div>
                {data.validation && (
                  <div className="validation-info">
                    <p><strong>Quality Score:</strong> {(data.validation.quality_score * 100).toFixed(1)}%</p>
                    <p><strong>Words:</strong> {data.validation.word_count}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Questions Tab
  const QuestionsTab = () => (
    <div className="tab-content">
      <h2>Research Questions</h2>

      <form onSubmit={handleGenerateQuestions} className="form">

        <div className="form-group">
          <label>Number of Questions per Category:</label>
          <input
            type="number"
            value={numQuestions}
            onChange={(e) => setNumQuestions(Math.max(1, parseInt(e.target.value) || 5))}
            min="1"
            max="10"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Generating...' : 'Generate Questions'}
        </button>
      </form>

      {Object.keys(questions).length > 0 && (
        <div className="results-section">
          <h3>Generated Questions</h3>
          <div className="questions-categories">
            {Object.entries(questions).map(([category, qs]) => (
              <div key={category} className="question-category">
                <h4>{category.charAt(0).toUpperCase() + category.slice(1)}</h4>
                <ul>
                  {qs.map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Metrics Tab
  const MetricsTab = () => (
    <div className="tab-content">
      <h2>Retrieval Evaluation</h2>

      <form onSubmit={handleEvaluate} className="form">
        <div className="form-group">
          <label>Relevant Document IDs (comma-separated):</label>
          <input
            type="text"
            value={relevantDocIds}
            onChange={(e) => setRelevantDocIds(e.target.value)}
            placeholder="e.g., 0, 1, 3, 5"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Evaluating...' : 'Evaluate'}
        </button>
      </form>

      {evaluationResults && (
        <div className="results-section">
          <h3>Evaluation Results</h3>
          <div className="metrics-grid">
            {Object.entries(evaluationResults.metrics || {}).map(([metric, value]) => (
              <div key={metric} className="metric-card">
                <h4>{metric}</h4>
                <p className="metric-value">
                  {typeof value === 'number' ? value.toFixed(3) : value}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Upload Tab
  const UploadTab = () => (
    <div className="tab-content">
      <h2>Document Management</h2>

      <div className="upload-section">
        <div className="upload-area">
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            disabled={loading}
            id="file-input"
          />
          <label htmlFor="file-input" className="upload-label">
            {loading ? 'Uploading and generating summaries...' : 'Click to upload PDF'}
          </label>
        </div>

        <button onClick={handleClearAll} className="btn btn-danger" disabled={loading || documents.length === 0}>
          Clear All Documents
        </button>
      </div>

      {/* Display auto-generated summaries */}
      {lastUploadSummaries && (
        <div className="auto-summaries-section">
          <h3>Auto-Generated Summaries - {lastUploadSummaries.filename}</h3>
          <p className="timestamp">Generated at: {lastUploadSummaries.timestamp}</p>

          <div className="summaries-grid">
            {Object.entries(lastUploadSummaries.summaries).map(([level, data]) => (
              <div key={level} className="summary-card auto-generated">
                <h4>{level.charAt(0).toUpperCase() + level.slice(1)} Level</h4>
                <div className="summary-content">
                  <p>{data.text}</p>
                </div>
                <div className="validation-info">
                  <p><strong>Quality Score:</strong> <span style={{ color: data.quality_score > 0.7 ? '#4CAF50' : '#FF9800' }}>{(data.quality_score * 100).toFixed(1)}%</span></p>
                  <p><strong>Word Count:</strong> {data.word_count}</p>
                  <p><strong>Status:</strong> <span style={{ fontWeight: 'bold', color: data.status === 'pass' ? '#4CAF50' : '#FF9800' }}>{data.status}</span></p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {documents.length > 0 && (
        <div className="documents-list">
          <h3>Uploaded Documents ({documents.length})</h3>
          {documents.map((doc, idx) => (
            <div key={idx} className="doc-item">
              <span className="doc-name">{doc.filename}</span>
              <span className="doc-pages">{doc.num_pages} pages</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="research-assistant-container">
      <header className="header">
        <h1> Research Assistant Bot</h1>
        <p>Research with retrieval, summarization, and question generation</p>
      </header>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <nav className="tabs">
        <button
          className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          Dashboard
        </button>
        <button
          className={`tab-button ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          Upload
        </button>
        <button
          className={`tab-button ${activeTab === 'query' ? 'active' : ''}`}
          onClick={() => setActiveTab('query')}
        >
          Query
        </button>
        <button
          className={`tab-button ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>
        <button
          className={`tab-button ${activeTab === 'questions' ? 'active' : ''}`}
          onClick={() => setActiveTab('questions')}
        >
          Questions
        </button>
        <button
          className={`tab-button ${activeTab === 'metrics' ? 'active' : ''}`}
          onClick={() => setActiveTab('metrics')}
        >
          Metrics
        </button>
      </nav>

      <main className="main-content">
        {activeTab === 'dashboard' && <DashboardTab />}
        {activeTab === 'upload' && <UploadTab />}
        {activeTab === 'query' && <QueryTab />}
        {activeTab === 'summary' && <SummaryTab />}
        {activeTab === 'questions' && <QuestionsTab />}
        {activeTab === 'metrics' && <MetricsTab />}
      </main>
    </div>
  );
};

export default ResearchAssistantUI;
