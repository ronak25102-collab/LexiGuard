import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error);
    const detail = error.response?.data?.detail;
    return Promise.reject(new Error(detail || error.message || 'Request failed.'));
  }
);

export const queryContract = (question, contractFilter = null) => {
  return apiClient.post('/process', { question, contract_filter: contractFilter });
};

export const getContracts = () => {
  return apiClient.get('/contracts');
};

export const getContractDetail = (contractId) => {
  return apiClient.get(`/contracts/${encodeURIComponent(contractId)}`);
};

export const getGraphStats = () => {
  return apiClient.get('/graph/stats');
};

export const healthCheck = () => {
  return apiClient.get('/health');
};

export const uploadContract = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await axios.post(`${import.meta.env.VITE_API_URL || '/api'}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 30000, // 30 second timeout for upload
    });
    return response.data;
  } catch (error) {
    console.error('Upload error:', error);
    if (error.code === 'ECONNABORTED') {
      throw new Error('Upload timed out. Please try again.');
    }
    throw error;
  }
};

export const checkContractStatus = (contractId) => {
  return apiClient.get(`/contracts/${encodeURIComponent(contractId)}/status`);
};

export const getEvaluationResults = () => {
  return apiClient.get('/evaluation/results');
};

export default apiClient;
