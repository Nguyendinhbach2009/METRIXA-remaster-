BEGIN;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS staging.raw_papers (
    paper_id TEXT NOT NULL,
    title TEXT,
    abstract TEXT,
    fields_of_study_raw TEXT,
    predicted_fields_raw TEXT,
    main_fields_raw TEXT,
    pdf_urls_raw TEXT,
    authors_raw TEXT,
    source_csv TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_raw_papers_paper_id
    ON staging.raw_papers (paper_id);

CREATE TABLE IF NOT EXISTS staging.raw_affiliations (
    paper_id TEXT NOT NULL,
    author_name TEXT,
    affiliations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_json TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_raw_affiliations_paper_id
    ON staging.raw_affiliations (paper_id);

CREATE TABLE IF NOT EXISTS core.papers (
    paper_id TEXT PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    fields_of_study JSONB NOT NULL DEFAULT '[]'::jsonb,
    predicted_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    main_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    pdf_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS core.authors (
    author_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS core.universities (
    university_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    website TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS core.paper_authors (
    paper_id TEXT NOT NULL REFERENCES core.papers(paper_id) ON DELETE CASCADE,
    author_id BIGINT NOT NULL REFERENCES core.authors(author_id) ON DELETE CASCADE,
    university_id BIGINT NOT NULL REFERENCES core.universities(university_id) ON DELETE CASCADE,
    author_order INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (paper_id, author_id, university_id)
);

CREATE INDEX IF NOT EXISTS idx_core_paper_authors_university
    ON core.paper_authors (university_id);

CREATE TABLE IF NOT EXISTS core.paper_subfields (
    paper_id TEXT NOT NULL REFERENCES core.papers(paper_id) ON DELETE CASCADE,
    subfield TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (paper_id, subfield)
);

CREATE INDEX IF NOT EXISTS idx_core_paper_subfields_subfield
    ON core.paper_subfields (subfield);

CREATE TABLE IF NOT EXISTS core.paper_mainfields (
    paper_id TEXT NOT NULL REFERENCES core.papers(paper_id) ON DELETE CASCADE,
    mainfield TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (paper_id, mainfield)
);

CREATE INDEX IF NOT EXISTS idx_core_paper_mainfields_mainfield
    ON core.paper_mainfields (mainfield);

CREATE OR REPLACE FUNCTION core.safe_jsonb_array(input_text TEXT)
RETURNS JSONB
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    trimmed TEXT;
BEGIN
    IF input_text IS NULL THEN
        RETURN '[]'::jsonb;
    END IF;

    trimmed := btrim(input_text);

    IF trimmed = '' OR lower(trimmed) = 'none' OR lower(trimmed) = 'null' THEN
        RETURN '[]'::jsonb;
    END IF;

    BEGIN
        RETURN trimmed::jsonb;
    EXCEPTION
        WHEN OTHERS THEN
            BEGIN
                RETURN replace(trimmed, '''', '"')::jsonb;
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN '[]'::jsonb;
            END;
    END;
END;
$$;

CREATE OR REPLACE FUNCTION core.normalize_org_name(input_name TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT NULLIF(
        btrim(
            regexp_replace(
                regexp_replace(coalesce(input_name, ''), '\s+', ' ', 'g'),
                '^[,.\-:\s]+|[,.\-:\s]+$',
                '',
                'g'
            )
        ),
        ''
    );
$$;

CREATE OR REPLACE FUNCTION core.is_informative_org(input_name TEXT)
RETURNS BOOLEAN
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT
        input_name IS NOT NULL
        AND length(btrim(input_name)) >= 4
        AND btrim(input_name) !~* '^\d'
        AND (
            btrim(input_name) !~* '^\s*(department|dept|division|section)\b'
            OR btrim(input_name) ~* '\b(university|univ|hospital|institute|college|faculty|centre|center)\b'
        );
$$;

CREATE OR REPLACE PROCEDURE core.rebuild_core_from_staging()
LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE
        core.paper_authors,
        core.paper_subfields,
        core.paper_mainfields,
        core.authors,
        core.universities,
        core.papers
    RESTART IDENTITY;

    INSERT INTO core.papers (
        paper_id,
        title,
        abstract,
        fields_of_study,
        predicted_fields,
        main_fields,
        pdf_urls,
        created_at,
        updated_at
    )
    SELECT
        rp.paper_id,
        NULLIF(btrim(rp.title), ''),
        NULLIF(btrim(rp.abstract), ''),
        core.safe_jsonb_array(rp.fields_of_study_raw),
        core.safe_jsonb_array(rp.predicted_fields_raw),
        core.safe_jsonb_array(rp.main_fields_raw),
        core.safe_jsonb_array(rp.pdf_urls_raw),
        NOW(),
        NOW()
    FROM (
        SELECT DISTINCT ON (paper_id)
            paper_id,
            title,
            abstract,
            fields_of_study_raw,
            predicted_fields_raw,
            main_fields_raw,
            pdf_urls_raw
        FROM staging.raw_papers
        WHERE NULLIF(btrim(paper_id), '') IS NOT NULL
        ORDER BY paper_id, loaded_at DESC
    ) rp;

    INSERT INTO core.paper_subfields (paper_id, subfield)
    SELECT
        rp.paper_id,
        btrim(sf.subfield)
    FROM (
        SELECT DISTINCT ON (paper_id)
            paper_id,
            predicted_fields_raw
        FROM staging.raw_papers
        WHERE NULLIF(btrim(paper_id), '') IS NOT NULL
        ORDER BY paper_id, loaded_at DESC
    ) rp
    CROSS JOIN LATERAL jsonb_array_elements_text(core.safe_jsonb_array(rp.predicted_fields_raw)) AS sf(subfield)
    WHERE NULLIF(btrim(sf.subfield), '') IS NOT NULL
    ON CONFLICT DO NOTHING;

    INSERT INTO core.paper_mainfields (paper_id, mainfield)
    SELECT
        rp.paper_id,
        btrim(mf.mainfield)
    FROM (
        SELECT DISTINCT ON (paper_id)
            paper_id,
            main_fields_raw,
            fields_of_study_raw
        FROM staging.raw_papers
        WHERE NULLIF(btrim(paper_id), '') IS NOT NULL
        ORDER BY paper_id, loaded_at DESC
    ) rp
    CROSS JOIN LATERAL jsonb_array_elements_text(
        CASE
            WHEN jsonb_array_length(core.safe_jsonb_array(rp.main_fields_raw)) > 0
                THEN core.safe_jsonb_array(rp.main_fields_raw)
            ELSE core.safe_jsonb_array(rp.fields_of_study_raw)
        END
    ) AS mf(mainfield)
    WHERE NULLIF(btrim(mf.mainfield), '') IS NOT NULL
    ON CONFLICT DO NOTHING;

    WITH normalized_aff AS (
        SELECT
            ra.paper_id,
            NULLIF(btrim(ra.author_name), '') AS author_name,
            core.normalize_org_name(ra.affiliations_json ->> 0) AS university_name,
            row_number() OVER (
                PARTITION BY ra.paper_id
                ORDER BY ra.loaded_at ASC, ra.author_name ASC, ra.paper_id ASC
            ) AS author_order
        FROM staging.raw_affiliations ra
        WHERE NULLIF(btrim(ra.paper_id), '') IS NOT NULL
    )
    INSERT INTO core.authors (name)
    SELECT DISTINCT na.author_name
    FROM normalized_aff na
    WHERE na.author_name IS NOT NULL
    ON CONFLICT (name) DO NOTHING;

    WITH normalized_aff AS (
        SELECT
            ra.paper_id,
            NULLIF(btrim(ra.author_name), '') AS author_name,
            core.normalize_org_name(ra.affiliations_json ->> 0) AS university_name
        FROM staging.raw_affiliations ra
        WHERE NULLIF(btrim(ra.paper_id), '') IS NOT NULL
    )
    INSERT INTO core.universities (name)
    SELECT DISTINCT na.university_name
    FROM normalized_aff na
    WHERE na.university_name IS NOT NULL
      AND core.is_informative_org(na.university_name)
    ON CONFLICT (name) DO NOTHING;

    WITH normalized_aff AS (
        SELECT
            ra.paper_id,
            NULLIF(btrim(ra.author_name), '') AS author_name,
            core.normalize_org_name(ra.affiliations_json ->> 0) AS university_name,
            row_number() OVER (
                PARTITION BY ra.paper_id
                ORDER BY ra.loaded_at ASC, ra.author_name ASC, ra.paper_id ASC
            ) AS author_order
        FROM staging.raw_affiliations ra
        WHERE NULLIF(btrim(ra.paper_id), '') IS NOT NULL
    ),
    dedup AS (
        SELECT
            na.paper_id,
            na.author_name,
            na.university_name,
            min(na.author_order)::int AS author_order
        FROM normalized_aff na
        WHERE na.author_name IS NOT NULL
          AND na.university_name IS NOT NULL
          AND core.is_informative_org(na.university_name)
        GROUP BY na.paper_id, na.author_name, na.university_name
    )
    INSERT INTO core.paper_authors (
        paper_id,
        author_id,
        university_id,
        author_order
    )
    SELECT
        d.paper_id,
        a.author_id,
        u.university_id,
        d.author_order
    FROM dedup d
    INNER JOIN core.papers p
        ON p.paper_id = d.paper_id
    INNER JOIN core.authors a
        ON a.name = d.author_name
    INNER JOIN core.universities u
        ON u.name = d.university_name
    ON CONFLICT (paper_id, author_id, university_id) DO NOTHING;
END;
$$;

DROP MATERIALIZED VIEW IF EXISTS core.mv_subfield_university_ranking;
CREATE MATERIALIZED VIEW core.mv_subfield_university_ranking AS
WITH author_counts AS (
    SELECT
        pa.paper_id,
        count(*)::numeric AS num_authors
    FROM core.paper_authors pa
    GROUP BY pa.paper_id
),
subfield_counts AS (
    SELECT
        ps.paper_id,
        count(*)::numeric AS num_subfields
    FROM core.paper_subfields ps
    GROUP BY ps.paper_id
),
weights AS (
    SELECT
        pa.paper_id,
        pa.university_id,
        ps.subfield,
        1.0 / NULLIF(ac.num_authors * sc.num_subfields, 0) AS contribution
    FROM core.paper_authors pa
    INNER JOIN core.paper_subfields ps
        ON ps.paper_id = pa.paper_id
    INNER JOIN author_counts ac
        ON ac.paper_id = pa.paper_id
    INNER JOIN subfield_counts sc
        ON sc.paper_id = pa.paper_id
)
SELECT
    w.subfield,
    w.university_id,
    sum(w.contribution)::double precision AS total_contribution,
    rank() OVER (
        PARTITION BY w.subfield
        ORDER BY sum(w.contribution) DESC
    ) AS rank
FROM weights w
GROUP BY w.subfield, w.university_id;

CREATE INDEX IF NOT EXISTS idx_mv_subfield_university_ranking_subfield_rank
    ON core.mv_subfield_university_ranking (subfield, rank);

DROP MATERIALIZED VIEW IF EXISTS core.mv_overall_university_contribution;
CREATE MATERIALIZED VIEW core.mv_overall_university_contribution AS
WITH author_counts AS (
    SELECT
        pa.paper_id,
        count(*)::numeric AS num_authors
    FROM core.paper_authors pa
    GROUP BY pa.paper_id
),
weights AS (
    SELECT
        pa.paper_id,
        pa.university_id,
        1.0 / NULLIF(ac.num_authors, 0) AS contribution
    FROM core.paper_authors pa
    INNER JOIN author_counts ac
        ON ac.paper_id = pa.paper_id
)
SELECT
    w.university_id,
    sum(w.contribution)::double precision AS total_contribution,
    rank() OVER (
        ORDER BY sum(w.contribution) DESC
    ) AS rank
FROM weights w
GROUP BY w.university_id;

CREATE INDEX IF NOT EXISTS idx_mv_overall_university_contribution_rank
    ON core.mv_overall_university_contribution (rank);

CREATE OR REPLACE VIEW core.v_subfield_university_ranking AS
SELECT
    m.subfield,
    u.name AS university,
    m.total_contribution,
    m.rank
FROM core.mv_subfield_university_ranking m
INNER JOIN core.universities u
    ON u.university_id = m.university_id;

CREATE OR REPLACE VIEW core.v_overall_university_ranking AS
SELECT
    u.name AS university,
    m.total_contribution,
    m.rank
FROM core.mv_overall_university_contribution m
INNER JOIN core.universities u
    ON u.university_id = m.university_id;

COMMIT;
