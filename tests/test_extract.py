from jobhunt.extract import extract


def test_extract_languages_and_skills():
    text = """
    We're looking for a senior backend engineer with 5+ years experience.
    You should know Python, TypeScript, Go, and have built systems on AWS with Kubernetes.
    Bachelor's degree required. Remote-first team.
    """
    e = extract(text, title="Senior Backend Engineer")
    assert "python" in e.languages
    assert "typescript" in e.languages
    assert "go" in e.languages
    assert "aws" in e.skills
    assert "kubernetes" in e.skills
    assert e.level == "senior"
    assert e.remote == "remote"
    assert e.degree == "bachelors"
    assert e.min_years == 5


def test_extract_intern_and_no_degree():
    text = "Internship for students. No degree required. React and Node.js needed."
    e = extract(text, title="Software Engineering Intern")
    assert e.level == "intern"
    assert e.degree == "none"
    assert "react" in e.skills
    assert "nodejs" in e.skills


def test_extract_unknowns_when_silent():
    e = extract("We make widgets.", title="Widget Maker")
    assert e.level == "unknown"
    assert e.remote == "unknown"
    assert e.degree == "unknown"
    assert e.min_years is None
    assert e.languages == []
