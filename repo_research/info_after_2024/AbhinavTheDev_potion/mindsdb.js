import { runQuery, uploadNotesData } from "./utils/utils.js";

class MindsDBIntegration {
  constructor() {
    this.knowledgeBaseName = "notes_kb";
    this.agentName = "notes_assistant";
  }

  async createKnowledgeBase() {
    const query = `
      CREATE KNOWLEDGE_BASE IF NOT EXISTS notes_project.${this.knowledgeBaseName}
      USING
        embedding_model = {
          "provider": "azure_openai",
          "model_name" : "text-embedding-3-small",
          "api_key": "${process.env.embed_api_key}",
          "base_url": "${process.env.embed_api_base_url}",
          "api_version": "2024-04-01-preview"
        },
        reranking_model = {
          "provider": "azure_openai",
          "model_name" : "gpt-4o",
          "api_key": "${process.env.api_key}",
          "base_url": "${process.env.api_base_url}",
          "api_version": "2024-04-01-preview",
          "method": "multi-class"
        },
        metadata_columns = ['note_category', 'note_created_at'],
        content_columns = ['note_title', 'note_content'],
        id_column = 'id';
    `;
    const result = await runQuery(query);
    console.log("-------KB \n", result);
    return result;
  }

  async createSummaryModel() {
    const query = `
      CREATE MODEL IF NOT EXISTS notes_project.notes_summarizer
      PREDICT summary
      USING
        engine = 'google_gemini_engine',
        model_name = 'gemini-2.0-flash',
        prompt_template = 'Please provide a concise summary of the following note:
        Title: {{note_title}}
        Content: {{note_content}}
        category: {{note_category}}
        Provide a clear, concise summary in 2-3 sentences:';
    `;
    const result = await runQuery(query);
    console.log("--------AI Model/Table \n", result);
    return result;
  }

  async createNotesAgent() {
    const query = `
      CREATE AGENT IF NOT EXISTS notes_project.${this.agentName}
      USING
        model = 'gemini-2.0-flash',
        google_api_key = '${process.env.google_api_key}',
        include_knowledge_bases = ['notes_project.${this.knowledgeBaseName}'],
        include_tables=['files.notes_data'],
        prompt_template = 'You are a smart notes assistant with access to the user\\'s note collection. You can:

        1. 🔍 Search and find specific notes using the knowledge base
        2. 📝 Summarize individual notes or groups of notes
        3. 📂 Suggest categories for new notes
        4. 📊 Provide insights and statistics about the note collection
        5. 💡 Answer questions about the notes content
        
        Always be helpful, accurate, and provide specific information from the notes when possible. 
        If you cannot find relevant information, clearly state that.';
    `;
    const result = await runQuery(query);
    console.log("--------AI Agent \n", result);
    return result;
  }

  async createSummaryJob() {
    const query = `
      CREATE JOB IF NOT EXISTS notes_project.daily_notes_summary
      AS (
        INSERT INTO files.daily_summaries
        SELECT 
          DATE(note_created_at) as summary_date,
          COUNT(*) as notes_created,
          COUNT(DISTINCT note_category) as categories_used,
          SUM(word_count) as total_words,
          'Daily summary generated' as daily_overview
        FROM files.notes_data
        WHERE DATE(note_created_at) = CURRENT_DATE
        GROUP BY DATE(note_created_at)
      )
      START NOW
      EVERY 1 day;
    `;
    return await runQuery(query);
  }

  // Get summary for existing note by ID
  async getSummary(noteId) {
    const query = `
      SELECT summary
      FROM notes_project.notes_summarizer
      WHERE note_title = (SELECT note_title FROM files.notes_data WHERE id = ${noteId})
      AND note_content = (SELECT note_content FROM files.notes_data WHERE id = ${noteId})
      AND note_category = (SELECT note_category FROM files.notes_data WHERE id = ${noteId});
    `;
    return await runQuery(query);
  }

  // Generate new summary for given content
  async generateSummary(title, content, category = "") {
    const query = `
      SELECT summary
      FROM notes_project.notes_summarizer
      WHERE note_title = '${title.replace(/'/g, "''")}'
      AND note_content = '${content.replace(/'/g, "''")}'
      AND note_category = '${category}';
    `;
    return await runQuery(query);
  }

  async insertIntoKB() {
    const query = `
      INSERT INTO notes_project.${this.knowledgeBaseName}
      SELECT id, note_title, note_content, note_category, note_created_at
      FROM files.notes_data;
    `;
    return await runQuery(query);
  }

  async searchNotes(searchTerm) {
    const query = `
      SELECT *
      FROM notes_project.${this.knowledgeBaseName}
      WHERE content = '${searchTerm.replace(/'/g, "''")}'
      LIMIT 10;
    `;
    return await runQuery(query);
  }

  async chatWithAgent(message) {
    const query = `
      SELECT answer
      FROM notes_project.${this.agentName}
      WHERE question = '${message.replace(/'/g, "''")}';
    `;
    return await runQuery(query);
  }

  async initializeMindsDB(notes = []) {
    try {
      let uploadResult;
      // 1. Upload initial notes data
      if (notes.length > 0) {
        uploadResult = await uploadNotesData(notes);
      }
      if (uploadResult.success) {
        // 2. Create Knowledge Base
        await this.createKnowledgeBase();

        // 3. Insert data into KB
        const KBresult = await this.insertIntoKB();

        if (KBresult.success) {
          // 4. Create AI Models
          await this.createSummaryModel();

          // 5. Create Agent
          await this.createNotesAgent();

          // 6. Create Jobs
          await this.createSummaryJob();
        } else {
          throw new Error("Failed to insert data into Knowledge Base", KBresult.error);
        }
      } else {
        throw new Error("Failed to upload notes data", uploadResult.error);
      }

      console.log("✅ MindsDB services started!");
      return { success: true, message: "MindsDB initialized successfully" };
    } catch (error) {
      console.error("❌ MindsDB service failed:", error);
      return { success: false, error: error.message };
    }
  }
}

export default MindsDBIntegration;
