from sqlalchemy import Column, String, Integer, JSON, LargeBinary, DateTime, func
from app.core.database import Base


class OptimizationJob(Base):
    """
    A resumable NSGA-II optimization run.

    Deliberately NOT run in a single request/BackgroundTask: serverless
    hosts (this app targets Vercel) freeze or kill the function process
    shortly after a response is sent, so work "backgrounded" after
    returning a response is not reliably guaranteed to finish. Instead the
    pymoo Algorithm object is checkpointed (pickled) between requests, and
    each POST .../step call resumes it for a small, time-boxed number of
    generations before saving state back and returning -- so the job
    advances across many short-lived requests instead of one long one.

    NOTE: with the default sqlite database_url this only works reliably
    while a single warm serverless instance is handling both create() and
    every subsequent step() -- Vercel does not guarantee /tmp persistence
    across invocations. For production use, point DATABASE_URL at a real
    Postgres instance (e.g. Supabase) so job state survives regardless of
    which instance picks up the next request.
    """
    __tablename__ = "optimization_jobs"

    id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False, default="pending")  # pending|running|completed|failed

    # Original request, kept for reference/debugging.
    request_json = Column(JSON, nullable=False)

    population_size = Column(Integer, nullable=False)
    n_generations = Column(Integer, nullable=False)
    generations_completed = Column(Integer, nullable=False, default=0)
    n_evaluated = Column(Integer, nullable=False, default=0)

    # Pickled pymoo Algorithm (+ Problem) checkpoint. Cleared once the job
    # reaches a terminal state to avoid keeping a large blob around forever.
    state_blob = Column(LargeBinary, nullable=True)

    pareto_front_json = Column(JSON, nullable=True)
    generation_history_json = Column(JSON, nullable=False, default=list)
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())