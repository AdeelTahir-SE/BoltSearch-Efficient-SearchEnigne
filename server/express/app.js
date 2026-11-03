import './env.js';
import express from 'express';
import cors from 'cors';
import router from './route.js';

const app = express();
app.disable('x-powered-by');
app.use(cors({ origin: process.env.CLIENT_ORIGIN || 'http://localhost:5173', exposedHeaders: ['X-Retrieval-Mode', 'X-Has-More', 'X-Page'] }));
app.use(express.json({ limit: '1mb' }));
app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
app.use('/api', router);
app.use((error, req, res, next) => {
  console.error(error.message);
  if (res.headersSent) return next(error);
  res.status(error.type === 'entity.parse.failed' ? 400 : 500).json({ error: error.type === 'entity.parse.failed' ? 'Invalid JSON request.' : 'An unexpected server error occurred.' });
});
export default app;
