export interface Question {
  id: number
  content: string
  reference_answer: string
  created_at: string
}

export interface QuestionListItem extends Question {
  summary: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export type ExamDisplayStatus =
  | 'incomplete'
  | 'grading'
  | 'excellent'
  | 'pass'
  | 'fail'

export interface ExamListItem {
  id: number
  email: string
  candidate_name: string | null
  created_at: string
  completed_at: string | null
  total_score: number | null
  status: ExamDisplayStatus
  question_count: number
  duration_minutes: number
}

export interface ExamDetail extends ExamListItem {
  candidate_phone: string | null
  started_at: string | null
  questions: {
    sort_order: number
    question_content: string
    answer_text: string | null
    submitted_at: string | null
    score: number | null
    feedback: string | null
    grading_status: string
  }[]
}

export interface ExamCreateResult {
  id: number
  email: string
  question_count: number
  duration_minutes: number
  created_at: string
  link: string
}

/** GET /exams/info?t=<link token> */
export interface ExamInfoResponse {
  completed: boolean
  started?: boolean
  question_count?: number
  duration_minutes?: number
  remaining_seconds?: number
}

/** POST /exams/begin */
export interface ExamStartResult {
  exam_id: number
  session_token: string
  started_at: string
  remaining_seconds: number
  question_count: number
}

/** GET /exams/current-question */
export interface CurrentQuestion {
  sort_order: number
  question_content: string
  question_number: number
  question_count: number
  remaining_seconds: number
}
