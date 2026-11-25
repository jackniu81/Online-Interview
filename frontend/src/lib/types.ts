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
