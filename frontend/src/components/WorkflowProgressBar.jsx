import React from "react";

const STAGES = [
  { key: "INITIATED", label: "Initiated", match: ["DRAFT", "OPEN", "IN_REVIEW", "APPROVED", "REJECTED", "CLOSED"] },
  { key: "REVIEW", label: "Review", match: ["IN_REVIEW", "APPROVED", "REJECTED", "CLOSED"] },
  { key: "APPROVAL", label: "QA Approval", match: ["APPROVED", "CLOSED"] },
  { key: "CLOSED", label: "Closed", match: ["CLOSED"] },
];

export default function WorkflowProgressBar({ status }) {
  const isComplete = (s) => s.match.includes(status);
  const isCurrent = (s, i) => {
    if (status === "REJECTED") return s.key === "REVIEW";
    if (status === "OPEN") return s.key === "REVIEW";
    if (status === "IN_REVIEW") return s.key === "APPROVAL";
    if (status === "APPROVED") return s.key === "CLOSED";
    if (status === "CLOSED") return s.key === "CLOSED";
    if (status === "DRAFT") return s.key === "INITIATED";
    return false;
  };
  const rejected = status === "REJECTED";

  return (
    <div className="flex items-center w-full mt-3" data-testid="workflow-progress">
      {STAGES.map((s, i) => {
        const done = isComplete(s);
        const current = isCurrent(s, i);
        return (
          <React.Fragment key={s.key}>
            <div className="flex flex-col items-center min-w-0" data-testid={`workflow-stage-${s.key}`}>
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold border-2 ${
                  rejected && s.key === "REVIEW" ? "bg-red-100 border-red-600 text-red-700" :
                  done ? "bg-slate-900 border-slate-900 text-white" :
                  current ? "bg-white border-slate-900 text-slate-900" :
                  "bg-white border-slate-300 text-slate-400"
                }`}
              >
                {done ? "✓" : i + 1}
              </div>
              <div className={`text-[10px] mt-1 uppercase tracking-wide mono ${done || current ? "text-slate-900" : "text-slate-400"}`}>{s.label}</div>
            </div>
            {i < STAGES.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 ${done ? "bg-slate-900" : "bg-slate-200"}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
