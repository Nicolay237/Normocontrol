export interface ReportIssue {
  readonly location: string
  readonly message: string
}

export interface ReportCategory {
  readonly name: string
  readonly issues: readonly ReportIssue[]
}

export interface CheckReport {
  readonly filename: string
  readonly generatedAt: string
  readonly isClean: boolean
  readonly totalIssues: number
  readonly notes: readonly string[]
  readonly categories: readonly ReportCategory[]
}

export interface ApiErrorPayload {
  readonly error: string
}
