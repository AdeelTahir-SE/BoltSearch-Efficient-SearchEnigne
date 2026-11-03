import app from './app.js';
app.listen(process.env.PORT || 3000, () => console.log(`Bolt Search listening on port ${process.env.PORT || 3000}`));
