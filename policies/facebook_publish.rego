package facebook.publish

default allow := false

allow if {
  input.publishing_enabled == true
  input.page_id != ""
  input.video_qc_passed == true
  input.originality_reviewed == true
  input.human_approved == true
  input.idempotency_key != ""
  input.published_count_24h < input.reels_daily_limit
}

deny[msg] if {
  input.human_approved != true
  msg := "human approval is required before publishing to Facebook"
}

deny[msg] if {
  input.video_qc_passed != true
  msg := "video QC must pass before publishing"
}

deny[msg] if {
  input.originality_reviewed != true
  msg := "originality/copyright review must pass before publishing"
}

deny[msg] if {
  input.published_count_24h >= input.reels_daily_limit
  msg := "Facebook Reels API publishing limit would be exceeded"
}
