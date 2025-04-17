const mongoose = require('mongoose');

const projectSchema = new mongoose.Schema({
  title: String,
  url: String,
  thumbnail: String,
  agency: String,
  tags: [String],
  source: String,
  scrapedAt: { type: Date, default: Date.now },
});

module.exports = mongoose.model('Project', projectSchema);
