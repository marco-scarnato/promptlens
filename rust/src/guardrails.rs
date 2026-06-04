use std::collections::HashMap;
use std::sync::OnceLock;

use once_cell::sync::Lazy;
use pyo3::prelude::*;
use rayon::prelude::*;
use regex::Regex;

// ── Static built-in rules ────────────────────────────────────────────────────

struct BuiltinRule {
    name: &'static str,
    pattern: &'static str,
}

static BUILTIN_DEFS: &[BuiltinRule] = &[
    // PII
    BuiltinRule { name: "email",                pattern: r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}" },
    BuiltinRule { name: "phone_it",             pattern: r"(?:\+39[\s\-]?)?(?:0\d{1,4}[\s\-]?\d{4,8}|3\d{2}[\s\-]?\d{6,7})" },
    BuiltinRule { name: "phone_international",  pattern: r"\+[1-9]\d{6,14}\b" },
    BuiltinRule { name: "fiscal_code_it",       pattern: r"(?i)[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]" },
    BuiltinRule { name: "credit_card",          pattern: r"\b(?:\d[ \-]?){12,15}\d\b" },
    BuiltinRule { name: "iban",                 pattern: r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b" },
    BuiltinRule { name: "ip_address",           pattern: r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b" },
    // Technical
    BuiltinRule { name: "sql_query",            pattern: r"(?i)\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b" },
    BuiltinRule { name: "base64",               pattern: r"[A-Za-z0-9+/]{20,}={0,2}" },
    BuiltinRule { name: "api_key",              pattern: r"[A-Za-z0-9_\-]{20,60}" },
    BuiltinRule { name: "code_block",           pattern: r"```[\s\S]*?```" },
    BuiltinRule { name: "url",                  pattern: r"https?://[^\s]+" },
];

// Compiled once at first use via OnceLock
static BUILTIN_REGEXES: OnceLock<Vec<(&'static str, Regex)>> = OnceLock::new();

fn builtin_regexes() -> &'static Vec<(&'static str, Regex)> {
    BUILTIN_REGEXES.get_or_init(|| {
        BUILTIN_DEFS
            .iter()
            .map(|r| (r.name, Regex::new(r.pattern).expect("invalid builtin regex")))
            .collect()
    })
}

// Set of builtin rule names — validated at GuardCore construction
static BUILTIN_NAMES: Lazy<std::collections::HashSet<&'static str>> = Lazy::new(|| {
    BUILTIN_DEFS.iter().map(|r| r.name).collect()
});

// ── CustomRule ────────────────────────────────────────────────────────────────

#[pyclass]
pub struct CustomRule {
    name: String,
    pattern: String,
    // compiled regex — not exposed to Python
    regex: Regex,
}

#[pymethods]
impl CustomRule {
    #[new]
    pub fn new(name: String, pattern: String) -> PyResult<Self> {
        let regex = Regex::new(&pattern).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Invalid regex pattern for rule '{}': {}",
                name, e
            ))
        })?;
        Ok(Self { name, pattern, regex })
    }

    #[getter]
    pub fn name(&self) -> &str {
        &self.name
    }

    #[getter]
    pub fn pattern(&self) -> &str {
        &self.pattern
    }

    fn __repr__(&self) -> String {
        format!("CustomRule(name='{}', pattern='{}')", self.name, self.pattern)
    }
}

// ── RuleMatch ─────────────────────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
pub struct RuleMatch {
    rule_name: String,
    matched_value: String,
    start: usize,
    end: usize,
}

#[pymethods]
impl RuleMatch {
    #[getter]
    pub fn rule_name(&self) -> &str {
        &self.rule_name
    }

    #[getter]
    pub fn matched_value(&self) -> &str {
        &self.matched_value
    }

    #[getter]
    pub fn start(&self) -> usize {
        self.start
    }

    #[getter]
    pub fn end(&self) -> usize {
        self.end
    }

    fn __repr__(&self) -> String {
        format!(
            "RuleMatch(rule='{}', value='{}', start={}, end={})",
            self.rule_name, self.matched_value, self.start, self.end
        )
    }
}

// ── GuardCore ─────────────────────────────────────────────────────────────────

#[pyclass]
pub struct GuardCore {
    // names of builtin rules to run
    builtin_rules: Vec<&'static str>,
    // compiled custom regex rules
    custom_rules: Vec<CustomRule>,
    // content keyword rules: category → keywords
    content_rules: Option<HashMap<String, Vec<String>>>,
}

#[pymethods]
impl GuardCore {
    /// Create a new GuardCore.
    ///
    /// Args:
    ///   rules:         list of builtin rule names (e.g. ["email", "phone_it"])
    ///   content_rules: optional dict[str, list[str]] — keyword categories
    ///   custom_rules:  optional list of CustomRule instances
    #[new]
    #[pyo3(signature = (rules, content_rules=None, custom_rules=None))]
    pub fn new(
        rules: Vec<String>,
        content_rules: Option<HashMap<String, Vec<String>>>,
        custom_rules: Option<Vec<PyRef<CustomRule>>>,
    ) -> PyResult<Self> {
        // Validate builtin rule names
        let mut builtin_rules: Vec<&'static str> = Vec::new();
        for name in &rules {
            match BUILTIN_NAMES.get(name.as_str()) {
                Some(static_name) => builtin_rules.push(static_name),
                None => {
                    return Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Unknown rule '{}'. Valid rules: {:?}",
                        name,
                        BUILTIN_NAMES.iter().collect::<Vec<_>>()
                    )));
                }
            }
        }

        // Clone custom rules out of PyRef
        let custom_rules_owned: Vec<CustomRule> = custom_rules
            .unwrap_or_default()
            .iter()
            .map(|r| {
                CustomRule {
                    name: r.name.clone(),
                    pattern: r.pattern.clone(),
                    regex: r.regex.clone(),
                }
            })
            .collect();

        Ok(Self {
            builtin_rules,
            custom_rules: custom_rules_owned,
            content_rules,
        })
    }

    /// Run all checks against *text* and return sorted RuleMatch list.
    pub fn check(&self, text: String) -> PyResult<Vec<RuleMatch>> {
        let regexes = builtin_regexes();

        // ── Builtin regex matches ────────────────────────────────────────────
        let builtin_matches: Vec<RuleMatch> = self
            .builtin_rules
            .par_iter()
            .flat_map(|rule_name| {
                let regex = regexes
                    .iter()
                    .find(|(n, _)| n == rule_name)
                    .map(|(_, r)| r)
                    .expect("builtin rule validated at construction");
                regex
                    .find_iter(&text)
                    .map(|m| RuleMatch {
                        rule_name: rule_name.to_string(),
                        matched_value: m.as_str().to_string(),
                        start: m.start(),
                        end: m.end(),
                    })
                    .collect::<Vec<_>>()
            })
            .collect();

        // ── Custom regex matches ─────────────────────────────────────────────
        let custom_matches: Vec<RuleMatch> = self
            .custom_rules
            .par_iter()
            .flat_map(|rule| {
                rule.regex
                    .find_iter(&text)
                    .map(|m| RuleMatch {
                        rule_name: rule.name.clone(),
                        matched_value: m.as_str().to_string(),
                        start: m.start(),
                        end: m.end(),
                    })
                    .collect::<Vec<_>>()
            })
            .collect();

        // ── Content keyword matches ──────────────────────────────────────────
        let content_matches: Vec<RuleMatch> = match &self.content_rules {
            None => vec![],
            Some(rules) => {
                let text_lower = text.to_lowercase();
                rules
                    .par_iter()
                    .flat_map(|(category, keywords)| {
                        keywords
                            .par_iter()
                            .flat_map(|kw| {
                                let kw_lower = kw.to_lowercase();
                                let mut hits = Vec::new();
                                let mut search_from = 0;
                                while let Some(pos) = text_lower[search_from..].find(&kw_lower) {
                                    let start = search_from + pos;
                                    let end = start + kw.len();
                                    hits.push(RuleMatch {
                                        rule_name: category.clone(),
                                        matched_value: text[start..end].to_string(),
                                        start,
                                        end,
                                    });
                                    search_from = start + 1;
                                }
                                hits
                            })
                            .collect::<Vec<_>>()
                    })
                    .collect()
            }
        };

        // ── Merge and sort by start position ─────────────────────────────────
        let mut all_matches: Vec<RuleMatch> = [builtin_matches, custom_matches, content_matches]
            .into_par_iter()
            .flatten()
            .collect();

        all_matches.sort_by_key(|m| m.start);
        Ok(all_matches)
    }
}

// ── Convenience wrappers (backwards compat) ───────────────────────────────────

/// True if the text contains any PII from the default PII ruleset.
#[pyfunction]
pub fn contains_pii(text: &str) -> bool {
    let pii_rules = ["email", "phone_it", "phone_international", "fiscal_code_it",
                     "credit_card", "iban", "ip_address"];
    let regexes = builtin_regexes();
    pii_rules.iter().any(|name| {
        regexes
            .iter()
            .find(|(n, _)| n == name)
            .map_or(false, |(_, r)| r.is_match(text))
    })
}

/// Replace all PII in text with "[REDACTED]".
#[pyfunction]
pub fn redact_pii(text: &str) -> String {
    let pii_rules = ["email", "phone_it", "phone_international", "fiscal_code_it",
                     "credit_card", "iban", "ip_address"];
    let regexes = builtin_regexes();
    let mut result = text.to_string();
    for name in &pii_rules {
        if let Some((_, r)) = regexes.iter().find(|(n, _)| n == name) {
            result = r.replace_all(&result, "[REDACTED]").into_owned();
        }
    }
    result
}

// ── register ──────────────────────────────────────────────────────────────────
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(contains_pii, m)?)?;
    m.add_function(wrap_pyfunction!(redact_pii, m)?)?;
    m.add_class::<CustomRule>()?;
    m.add_class::<RuleMatch>()?;
    m.add_class::<GuardCore>()?;
    Ok(())
}

