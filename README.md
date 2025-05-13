# GitInsight 
**GitInsight** is an intelligent web application designed to analyze GitHub repositories. It leverages the power of Google's Gemini AI to generate comprehensive, structured HTML summaries, helping you quickly understand the purpose, structure, and usage of any codebase. Features include GitHub OAuth for secure access to private repositories and a persistent history of your analyses. 
(this repository is still a WIP)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)
## ✨ Features 
* **AI-Powered Summaries:** Utilizes Google's Gemini Pro model to generate insightful summaries of repositories. 
* **📄 Structured HTML Output:** Summaries are delivered in well-formatted HTML, including sections for overview, key features, setup, usage, and architecture. 
* **🔗 GitHub Integration:** * Analyze public repositories in Guest Mode. * Log in with GitHub (OAuth 2.0) to analyze private repositories you have access to. 
* **⚙️ Customizable Analysis:** Tailor summaries by specifying: 
* Language (e.g., English, Spanish) 
* Length (Small, Medium, Large) 
* Technical Level (Non-Technical, Technical, Expert) 
* **⏱️ Real-time Progress:** Receive streaming updates during the analysis process (URL validation, cloning, parsing, AI generation). 
* **🗄️ Analysis History:** Logged-in users can view a history of their past analyses, including parameters used and the generated summary. 
* **🔒 Secure & Asynchronous:** Built with FastAPI, ensuring high performance for I/O-bound operations. Database interactions are handled asynchronously with SQLAlchemy and AsyncPG. 
* **🧹 Automatic Cleanup:** Temporary cloned repositories are automatically cleaned up after analysis. 
* **🧪 Well-Tested:** Includes a suite of unit and integration tests using Pytest. 
## 🛠️ Tech Stack 
* **Backend:** FastAPI, Uvicorn 
* **AI Model:** Google Gemini Pro (via `google-generativeai`) 
* **AI Tokenization:** `google-cloud-aiplatform[tokenization]` (Vertex AI) 
* **Database:** PostgreSQL 
* **ORM:** SQLAlchemy (async support) 
* **Driver:** AsyncPG 
* **Migrations (Optional):** Alembic (recommended for production) 
* **Authentication:** Authlib (GitHub OAuth) 
* **Templating:** Jinja2 
* **HTTP Client:** HTTPX (for OAuth interactions) 
* **Utilities:** `python-dotenv`, `itsdangerous` 
## 📂 Project Structure 
``` 
├── main.py # FastAPI application, routes, main logic 
├── requirements.txt # Project dependencies 
├── services/ 
│ ├── analyzer.py # AI summary generation logic (Gemini) 
│ ├── db_models.py # SQLAlchemy database models 
│ ├── db_service.py # Database interaction services 
│ ├── github.py # GitHub interaction (cloning, URL parsing) 
│ └── parser.py # Repository content parsing logic 
├── static/ │ ├── style.css # CSS styles 
│ └── github-mark.svg # GitHub icon 
├── templates/ 
│ ├── app.html # Main application page template 
│ └── index.html # Welcome/Login page template 
├── tests/ # Unit and integration tests 
│ ├── conftest.py 
│ ├── test_main_endpoints.py 
│ └── services/ 
│ ├── test_analyzer.py 
│ ├── test_github.py 
│ └── test_parser.py 
└── .env.example # Example environment variables file 
``` 
## ⚙️ Setup and Installation 
### Prerequisites 
* Python 3.9+ 
* Git 
* PostgreSQL Server (if using database features like history) 
### Steps 1. 
**Clone the repository:** 
```
bash git clone https://github.com/AhmedAbubaker98/GitInsight.git
cd gitinsight 
``` 
2. **Create and activate a virtual environment:** 
```
bash python -m venv venv 
source venv/bin/activate 
# On Windows: venv\Scripts\activate 
``` 
3. **Install dependencies:** 
```
bash pip install -r requirements.txt 
``` 
4. **Set up environment variables:** 
Create a `.env` file in the project root by copying `.env.example`: ```bash cp .env.example .env ``` Then, fill in the required values in your `.env` file. See the [Environment Variables](#-environment-variables) section for details. 
5. **Database Setup (if `DATABASE_URL` is configured):** 
* Ensure your PostgreSQL server is running and accessible. 
* The application will attempt to create the necessary tables on startup (`init_db()` in `main.py`'s lifespan event). 
* For production, it's highly recommended to use [Alembic](https://alembic.sqlalchemy.org/) for database migrations. `alembic` is listed as an optional dependency in `requirements.txt`. 
## 🚀 Running the Application 
Once the setup is complete, run the FastAPI application using Uvicorn: 
```
bash uvicorn main:app --reload --host 0.0.0.0 --port 8000 
``` 
The application will be accessible at `http://localhost:8000`. 
## 📖 How to Use 1. 
**Access the Web Interface:** 
Open your browser and go to `http://localhost:8000`. 
2. **Authentication:** 
* **Login with GitHub:** Click the "Login with GitHub" button. You'll be redirected to GitHub for authorization. This allows GitInsight to access repositories based on your permissions and enables the analysis history feature. 
* **Continue as Guest:** Click "Continue as Guest" to analyze public repositories without logging in. History will not be available in guest mode. 
3. **Analyze a Repository (Analyze Tab):** 
* Enter the **GitHub Repository URL** (e.g., `https://github.com/owner/repo`). 
* Select the desired **Summary Language**, **Summary Length**, and **Technical Level**. 
* Click "Analyze". 
4. **View Progress & Results:** 
* The "Analysis Progress" section will show real-time updates. 
* Once complete, the "Analysis Result" section will display the generated HTML summary. 
5. **View Analysis History (History Tab - Logged-in Users Only):** 
* If you are logged in and the database is configured, click the "History" tab. 
* A list of your past analyses will be displayed. 
* Click on an item to view its detailed summary. 
## 🔑 Environment Variables (this section is being continously updated)
Create a `.env` file in the project root with the following variables: 
```
# .env.example
# FastAPI Session Management
SESSION_SECRET="your_strong_random_session_secret_key" 
# Generate a strong secret key (e.g., using `openssl rand -hex 32`) 
# GitHub OAuth Application Credentials 
# Create a GitHub OAuth App: https://docs.github.com/en/developers/apps/building-oauth-apps/creating-an-oauth-app 
# Authorization callback URL should be: http://localhost:8000/auth/github (or your production URL) 
GITHUB_CLIENT_ID="your_github_oauth_client_id" GITHUB_CLIENT_SECRET="your_github_oauth_client_secret" 
# Google Generative AI API Key 
# Get your API key from Google AI Studio: https://aistudio.google.com/app/apikey MY_GOOGLE_API_KEY="your_google_ai_api_key" 
# Database Connection (PostgreSQL) 
# Example: postgresql+asyncpg://user:password@host:port/database 
# If not set, database features (like history) will be disabled. 
DATABASE_URL="postgresql+asyncpg://gitinsight_user:your_password@localhost:5432/gitinsight_db" 
# Optional: For AWS RDS PostgreSQL SSL connection 
# Path to the AWS Global Bundle CA certificate if needed for SSL connection to RDS. 
# Download from: https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem 
# AWS_GLOBAL_Bundle_CA="/path/to/your/global-bundle.pem" ``` 
**Important Notes:** 
* If `GITHUB_CLIENT_ID` or `GITHUB_CLIENT_SECRET` are not set, GitHub login will be disabled. 
* If `MY_GOOGLE_API_KEY` is not set, AI summary generation will fail. 
* If `DATABASE_URL` is not set, the analysis history feature will be disabled.
```

<!-- ## 🔎 How It Works 1. **User Interaction:** The user provides a GitHub repository URL and analysis preferences through the web UI (Jinja2 templates). 2. **Authentication (Optional):** If the user logs in with GitHub, an OAuth 2.0 flow is initiated using `Authlib`. An access token is stored in the session. 3. **Request Handling (FastAPI):** The `/analyze/repo` endpoint receives the request. 4. **URL Parsing (`services/github.py`):** The GitHub URL is parsed to extract the owner and repository name. 5. **Repository Cloning (`services/github.py`):** * If a GitHub token is available (logged-in user), it's used for authenticated cloning (HTTPS). * For guest users, an anonymous HTTPS clone is attempted. Local Git credential helpers are explicitly disabled to prevent interference with private repository cloning attempts. * The repository is cloned into a temporary local directory. 6. **Content Parsing (`services/parser.py`):** * The cloned repository is traversed. * "Important" files (READMEs, setup files like `requirements.txt`, `package.json`, etc.) are prioritized. * Source code files (based on extensions) are collected. * Binary files, ignored directories (e.g., `.git`, `node_modules`), and very large/small files are skipped. 7. **AI Summary Generation (`services/analyzer.py`):** * The collected text content is compiled into a prompt for Google's Gemini model. * The prompt instructs the AI to generate a structured HTML summary based on the user's preferences (language, length, technicality). * The `generate_summary_stream` function communicates with the Gemini API. 8. **Streaming Response:** * The FastAPI endpoint streams progress updates (e.g., "Cloning...", "Parsing...", "Generating summary...") and the final HTML summary back to the client as `application/x-ndjson`. * The frontend JavaScript updates the UI in real-time. 9. **Database Logging (`services/db_service.py` - Logged-in Users):** * If the user is logged in and the database is configured, the analysis request (URL, parameters, summary) is logged to the `analysis_history` table in PostgreSQL. 10. **Cleanup:** The temporary directory containing the cloned repository is deleted. ## 🗄️ Database GitInsight uses a PostgreSQL database to store analysis history for logged-in users. * **ORM:** [SQLAlchemy](https://www.sqlalchemy.org/) (with async support) is used for database interactions. * **Async Driver:** [AsyncPG](https://github.com/MagicStack/asyncpg) provides the asynchronous connection to PostgreSQL. * **Models (`services/db_models.py`):** * `AnalysisHistory`: Stores details of each analysis, including user ID, repository URL, timestamp, parameters used, and the generated summary. * **Service (`services/db_service.py`):** Contains functions for initializing the database, getting sessions, and performing CRUD operations on history records. * **Lifespan Management:** FastAPI's `lifespan` context manager is used to initialize the database schema (`init_db()`) on application startup and dispose of the database engine pool (`db_engine.dispose()`) on shutdown. * **Migrations:** While the application can create tables on startup, for production environments or schema changes, using [Alembic](https://alembic.sqlalchemy.org/) is highly recommended. `alembic` and `psycopg2-binary` (often needed by Alembic) are included in `requirements.txt`. ## 🧪 Testing The project includes a suite of tests using `pytest`. To run the tests: 1. Ensure you have installed development dependencies (pytest is in `requirements.txt`). 2. Make sure your environment variables (e.g., `SESSION_SECRET`) are set, or mocked appropriately in `tests/conftest.py` if needed for specific tests. The `conftest.py` provided already mocks some. 3. Run pytest from the project root: ```bash pytest ``` Tests cover: * FastAPI endpoints (`tests/test_main_endpoints.py`) * AI Analyzer service (`tests/services/test_analyzer.py`) * GitHub interaction service (`tests/services/test_github.py`) * Repository Parser service (`tests/services/test_parser.py`)  -->

## 🤝 Contributing 
Contributions are welcome! 
If you'd like to contribute, please follow these steps: 
1. Fork the repository. 
2. Create a new branch (`git checkout -b feature/your-feature-name`). 
3. Make your changes and commit them (`git commit -m 'Add some feature'`). 
4. Push to the branch (`git push origin feature/your-feature-name`). 
5. Open a Pull Request. Please ensure your code adheres to the existing style and that all tests pass. 
## 📄 License
This project is licensed under the BSL License - see the [LICENSE](LICENSE) file for details. 
--- Happy Analyzing!
