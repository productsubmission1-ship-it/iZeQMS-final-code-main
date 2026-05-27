#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Updates to existing iZeQMS (cloned from https://github.com/bharatgohil907-ai/iZeQMS-final-code.git):
  1) Module Framework — publish + version sync (when a framework is updated and published, the
     new version becomes available to every live module, and live records can be migrated.)
  2) Remove the static "Description / Impact Assessment / Root Cause / Proposed Action" blocks
     (those that previously rendered "— not provided —") from non-DEVIATION module record detail
     screens. Render dynamic framework form instead.
  3) PDF download for every module record (including user-entered data); log download in audit trail.
  4) "Other" option in dropdowns / radios — when selected, an inline text input appears to capture
     the custom value. Works in DynamicRecords creation form & DynamicFrameworkForm.
  5) Remove the Plants & Sites page + nav + plant selection (was confusing on a per-tenant install).
  6) New role created in Role Matrix automatically appears in the User creation dialog and Users
     filter — same behaviour as canonical roles.
  7) Audit Trail PDF download with footer "Printed by <name> (<email>) · timestamp · Page X of Y".
  8) URS izQMS.pdf compliance (PDF footer, audit immutability, audit-log for every action including
     PDF exports).

backend:
  - task: "Generic PDF generator (audit + dynamic + legacy record + reports)"
    implemented: true
    working: "NA"
    file: "/app/backend/generic_pdf.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Added build_legacy_record_pdf (Change Control / CAPA / Incident / Event)
          and build_reports_pdf (filtered records list + module x status summary
          + optional per-record workflow appendix). All PDFs share the same
          compliant footer "Printed by <name> (<email>) · <generated_at> · Page X of Y".

  - task: "/api/records/{id}/pdf endpoint (Download PDF for any legacy module)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Generic per-record PDF for legacy records. DEVIATION delegates to
          build_deviation_pdf (existing 9-Part renderer). Others (CC/CAPA/Incident/Event)
          render via build_legacy_record_pdf with bound framework template fields,
          workflow_events, comments and audit trail. Logs RECORD_PDF_EXPORT.

  - task: "/api/reports/pdf endpoint (Reports module PDF)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Mirrors /api/exports filters. Generates a PDF with summary table
          (by module x status), records table and optional per-record workflow
          appendix. Logs REPORTS_PDF_EXPORT in audit trail.

  - task: "/api/audit/pdf endpoint (Audit Trail PDF export, audit-logged)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          New GET /api/audit/pdf endpoint. Accepts same filters as /api/audit
          (entity_type, action, user_email, from_date, to_date, limit). Streams
          a PDF and logs an AUDIT_PDF_EXPORT entry in audit_trail.

  - task: "/api/module-framework/records/{id}/pdf endpoint (dynamic record PDF, audit-logged)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          New endpoint. Renders the bound template + form_data + history +
          per-record audit. Logs DYN_RECORD_PDF_EXPORT in audit trail.

  - task: "/api/module-framework/records/{id}/migrate-version endpoint"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Rebinds a dynamic record to the latest PUBLISHED version (same code,
          same plant_id) and writes a DYN_RECORD_MIGRATE_VERSION audit entry.
          Returns {ok:true, noop:true} when already on the latest.

frontend:
  - task: "Remove static Description/Impact/Root Cause/Proposed Action blocks from non-DEVIATION record detail"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/RecordDetail.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Removed the 4 DetailBlock elements that rendered '— not provided —' for empty fields.
          DynamicFrameworkForm now drives the form when a template is bound; otherwise an
          empty-state message is shown.

  - task: "Remove Plants & Sites page/nav/selector"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/App.js, ModuleFramework.jsx, TemplateDesigner.jsx, DynamicRecords.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Removed /plants route, "Manage Plants →" link, Plant filter and Plant column from the
          template list, hid the Plant scope selector in TemplateDesigner (defaults to GLOBAL),
          removed plant selector from the Create-record dialog (DynamicRecords auto-picks first
          active plant).

  - task: "PDF download buttons (Audit Trail page + per dynamic record)"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/AuditPage.jsx, DynamicRecords.jsx, RecordDetail.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Audit page has a 'Download PDF' button (uses /api/audit/pdf). DynamicRecords list rows
          show a FileDown icon button → /api/module-framework/records/{id}/pdf. Deviation detail
          page keeps its existing /deviations/{id}/pdf via a 'Download PDF' button.

  - task: "Other-option custom input in dropdowns/radios"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/DynamicRecords.jsx, components/DynamicFrameworkForm.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          When a dropdown/radio has 'Other' in its options and the user picks it, an inline
          text input is rendered. The stored value becomes { value: 'Other', other: '<text>' }.

  - task: "Dynamic roles auto-appear in User Create dialog and Users filter"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/NewUserDialog.jsx, pages/Users.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          NewUserDialog fetches /api/role-mgmt/roles?active=true on open and merges the
          custom roles with CANONICAL_ROLES; each renders as a toggle pill (custom roles
          marked with a small dot). Users.jsx filter dropdown does the same merge.

  - task: "Record version migration UI"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/DynamicRecords.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Shows '(vN avail.)' next to the template version column when a newer PUBLISHED version
          exists, and renders an ArrowUpCircle button that calls /migrate-version with confirm.

metadata:
  created_by: "main_agent"
  version: "2.0"
  test_sequence: 0
  run_ui: false

test_plan:
  current_focus:
    - "/api/audit/pdf endpoint (Audit Trail PDF export, audit-logged)"
    - "/api/module-framework/records/{id}/pdf endpoint (dynamic record PDF, audit-logged)"
    - "/api/module-framework/records/{id}/migrate-version endpoint"
    - "Remove static Description/Impact/Root Cause/Proposed Action blocks from non-DEVIATION record detail"
    - "Remove Plants & Sites page/nav/selector"
    - "PDF download buttons (Audit Trail page + per dynamic record)"
    - "Other-option custom input in dropdowns/radios"
    - "Dynamic roles auto-appear in User Create dialog and Users filter"
    - "Record version migration UI"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Cloned iZeQMS-final-code from GitHub into /app, restored .env, installed deps,
      backend and frontend up. Implemented all eight requested changes (publish/version sync
      via migrate-version + UI, drop empty static fields from record detail, generic PDF
      generator for any dynamic record + audit trail with "Printed by <user> · Page X of Y"
      footer, audit logging of every PDF download, "Other" inline text input in dropdowns/radios,
      removed Plants & Sites, dynamic roles auto-merged into user creation/filter UI).
      All backend PDF endpoints smoke-tested OK via curl (admin@izqms.com / Admin@2026).
      Please run focused regression + the above 9 features.