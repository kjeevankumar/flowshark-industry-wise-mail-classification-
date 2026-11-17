from app.db.session import SessionLocal
from app.models.email_model import Email
from app.services.hybrid_classifier import HybridClassifier
from app.services.rule_classifier import RuleBasedClassifier
from app.services.nlp_preprocessor import NLPPreprocessor
from app.services.context_service import ContextService
from app.services.llm_provider import get_llm_provider
from app.config import get_settings

db = SessionLocal()
settings = get_settings()

e = db.query(Email).filter(Email.id == 37).first()
print(f"Tracing Email {e.id}: {e.subject}")

nlp = NLPPreprocessor()
pre = nlp.preprocess(body_plain=e.body_text, body_html=e.body_html, subject=e.subject)
print(f"Preprocessed: is_promotional={pre.is_promotional}, cleaned_body len={len(pre.cleaned_body)}")

ctx_service = ContextService(db=db)
context = ctx_service.build_conversation_context(e)
print(f"Context: has_context={context.has_context}, contact_rel={context.contact_relationship}, lead_id={context.lead_id}")

rule_engine = RuleBasedClassifier()
rule_signals = rule_engine.evaluate(
    cleaned_body=pre.cleaned_body,
    subject=e.subject,
    is_reply=context.is_reply,
    has_thread_history=context.has_context,
    context=context
)
print(f"Rule signals: intent={rule_signals.intent}, rel={rule_signals.relationship}, stage={rule_signals.lead_stage}, conf={rule_signals.confidence}")

llm_provider = get_llm_provider(settings=settings)
output = llm_provider.classify_email(
    subject=e.subject,
    preprocessed=pre,
    thread_context=context.context_summary,
    rule_signals=rule_signals,
    context=context,
)
print(f"LLM Provider ({llm_provider.__class__.__name__}):")
print(f"  relationship={output.relationship}, intent={output.intent}, stage={output.lead_stage}, conf={output.confidence}")

# Trace HybridClassifier
hybrid = HybridClassifier(db=db, settings=settings)
res = hybrid.classify_email(e)
print(f"Hybrid Result for Email 37:")
print(f"  rel={res.relationship}, intent={res.intent}, stage={res.lead_stage}, conf={res.confidence}")

# Now trace Email 29 as well!
e29 = db.query(Email).filter(Email.id == 29).first()
print(f"\n--- Tracing Email 29: {e29.subject} ---")
pre29 = nlp.preprocess(body_plain=e29.body_text, body_html=e29.body_html, subject=e29.subject)
ctx29 = ctx_service.build_conversation_context(e29)
print(f"Context 29: has_context={ctx29.has_context}, contact_rel={ctx29.contact_relationship}, lead_id={ctx29.lead_id}, lead_stage={ctx29.lead_stage}")
rule29 = rule_engine.evaluate(
    cleaned_body=pre29.cleaned_body,
    subject=e29.subject,
    is_reply=ctx29.is_reply,
    has_thread_history=ctx29.has_context,
    context=ctx29
)
print(f"Rule signals 29: intent={rule29.intent}, rel={rule29.relationship}, stage={rule29.lead_stage}, conf={rule29.confidence}")

res29 = hybrid.classify_email(e29)
print(f"Hybrid Result for Email 29:")
print(f"  rel={res29.relationship}, intent={res29.intent}, stage={res29.lead_stage}, conf={res29.confidence}")

db.close()
