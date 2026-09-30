/**
 * Product Catalog Manager — story E2-S4 (AC-02, AC-11, AC-24), route `/admin/catalog`.
 *
 * ADMIN-only screen: lists the products, expands one to its rule-set versions, creates or replaces
 * the open DRAFT and publishes it behind a confirm dialog. The role guard here is convenience only —
 * the API is authoritative (403 FORBIDDEN).
 */
import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../api/client';
import { createDraft, listProducts, listVersions, publishVersion, replaceDraft } from '../api/catalog';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ProductTable } from '../components/ProductTable';
import { RuleFileEditor } from '../components/RuleFileEditor';
import { VersionTable } from '../components/VersionTable';
import { useRole } from '../app/RoleContext';
import { useIsNarrow } from '../app/useIsNarrow';
import { isFieldErrorDetails } from '../types/api';
import type {
  CatalogVersion,
  DraftEditorMode,
  FieldIssue,
  ProductCode,
  ProductSummary,
  RuleFileDraftBody,
} from '../types/catalog';

interface Banner {
  readonly code: string;
  readonly message: string;
}

function toBanner(error: unknown): Banner {
  if (error instanceof ApiError) return { code: error.code, message: error.message };
  return { code: 'UNKNOWN_ERROR', message: 'The request failed unexpectedly.' };
}

function toIssues(error: unknown): readonly FieldIssue[] {
  if (!(error instanceof ApiError) || error.code !== 'VALIDATION_ERROR') return [];
  if (isFieldErrorDetails(error.details)) return error.details;
  return [{ field: '$', code: 'SCHEMA_VIOLATION' }];
}

/** Seeds the editor from the newest version's rule file, bumped to the next DRAFT version. */
function seedDraft(product: ProductCode, versions: readonly CatalogVersion[]): string {
  const newest = [...versions].sort((a, b) => b.version - a.version)[0];
  const nextVersion = newest === undefined ? 1 : newest.version + 1;
  const base = newest?.rules ?? { product };
  return JSON.stringify({ ...base, product, version: nextVersion, status: 'DRAFT' }, null, 2);
}

function parseBody(text: string): RuleFileDraftBody | null {
  try {
    const parsed: unknown = JSON.parse(text);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return null;
    return parsed as RuleFileDraftBody;
  } catch {
    return null;
  }
}

export function CatalogPage(): JSX.Element {
  const { api, role } = useRole();
  const isNarrow = useIsNarrow();
  const isAdmin = role === 'ADMIN';

  const [products, setProducts] = useState<readonly ProductSummary[]>([]);
  const [loadError, setLoadError] = useState<Banner | null>(null);
  const [expanded, setExpanded] = useState<ProductCode | null>(null);
  const [versions, setVersions] = useState<readonly CatalogVersion[]>([]);
  const [banner, setBanner] = useState<Banner | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [issues, setIssues] = useState<readonly FieldIssue[]>([]);
  const [draftText, setDraftText] = useState('');
  const [mode, setMode] = useState<DraftEditorMode>({ kind: 'create' });
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<CatalogVersion | null>(null);

  const loadProducts = useCallback(async (): Promise<void> => {
    setLoadError(null);
    try {
      setProducts(await listProducts(api));
    } catch (error) {
      setLoadError(toBanner(error));
    }
  }, [api]);

  useEffect(() => {
    if (!isAdmin) return;
    void loadProducts();
  }, [isAdmin, loadProducts]);

  const loadVersions = useCallback(
    async (product: ProductCode, reseed: boolean): Promise<void> => {
      setBanner(null);
      try {
        const loaded = await listVersions(api, product);
        setVersions(loaded);
        if (reseed) {
          setDraftText(seedDraft(product, loaded));
          setMode({ kind: 'create' });
          setIssues([]);
        }
      } catch (error) {
        setBanner(toBanner(error));
      }
    },
    [api],
  );

  const onToggle = useCallback(
    (product: ProductCode): void => {
      setNotice(null);
      if (expanded === product) {
        setExpanded(null);
        setVersions([]);
        return;
      }
      setExpanded(product);
      void loadVersions(product, true);
    },
    [expanded, loadVersions],
  );

  const onSubmitDraft = useCallback(async (): Promise<void> => {
    if (expanded === null) return;
    setBanner(null);
    setNotice(null);
    const body = parseBody(draftText);
    if (body === null) {
      setIssues([{ field: '$', code: 'INVALID_JSON' }]);
      return;
    }
    setIssues([]);
    setBusy(true);
    try {
      const result =
        mode.kind === 'replace'
          ? await replaceDraft(api, expanded, mode.version, body)
          : await createDraft(api, expanded, body);
      setNotice(`${result.product} v${result.version} saved with status ${result.status}.`);
      await loadVersions(expanded, false);
      setMode({ kind: 'create' });
    } catch (error) {
      setIssues(toIssues(error));
      const asBanner = toBanner(error);
      if (asBanner.code !== 'VALIDATION_ERROR') setBanner(asBanner);
    } finally {
      setBusy(false);
    }
  }, [api, draftText, expanded, loadVersions, mode]);

  const onConfirmPublish = useCallback(async (): Promise<void> => {
    if (expanded === null || pending === null) return;
    const version = pending.version;
    setBusy(true);
    setBanner(null);
    setNotice(null);
    try {
      const result = await publishVersion(api, expanded, version);
      setPending(null);
      setNotice(`${result.product} v${result.version} published and now active.`);
      await Promise.all([loadVersions(expanded, false), loadProducts()]);
    } catch (error) {
      setPending(null);
      setBanner(toBanner(error));
    } finally {
      setBusy(false);
    }
  }, [api, expanded, loadProducts, loadVersions, pending]);

  const onEditDraft = useCallback((version: CatalogVersion): void => {
    setMode({ kind: 'replace', version: version.version });
    setIssues([]);
    setNotice(null);
    setDraftText(JSON.stringify(version.rules ?? { version: version.version }, null, 2));
  }, []);

  if (!isAdmin) {
    return (
      <section className="panel" data-testid="not-authorised">
        <h1>Not authorised</h1>
        <p>
          The selected demo user&apos;s role cannot open the Product Catalog. Switch the demo user to
          Admin in the header.
        </p>
      </section>
    );
  }

  const currency = products.find((item) => item.product === expanded)?.currency ?? 'INR';

  return (
    <div data-testid="catalog-page">
      <div className="page-head">
        <div>
          <h1>Product Catalog</h1>
          <p className="route">Route: /admin/catalog · rule-set versions per product</p>
        </div>
      </div>

      {loadError !== null ? (
        <div className="alert alert-error" role="alert" data-testid="load-error">
          <p>
            <strong className="code">{loadError.code}</strong> — {loadError.message}
          </p>
          <button
            type="button"
            className="btn btn-sm"
            data-testid="retry-products"
            onClick={() => void loadProducts()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {notice !== null ? (
        <p className="alert alert-ok" role="status" data-testid="op-notice">
          {notice}
        </p>
      ) : null}

      {banner !== null ? (
        <div className="alert alert-error" role="alert" data-testid={`banner-${banner.code}`}>
          <p>
            <strong className="code">{banner.code}</strong> — {banner.message}
          </p>
        </div>
      ) : null}

      <section aria-labelledby="products-h">
        <h2 id="products-h">Products</h2>
        <ProductTable
          products={products}
          expanded={expanded}
          isNarrow={isNarrow}
          onToggle={onToggle}
        />
      </section>

      {expanded !== null ? (
        <div id="versions-panel">
          <section className="panel" aria-labelledby="versions-h">
            <h2 id="versions-h">Versions — {expanded}</h2>
            <VersionTable
              product={expanded}
              currency={currency}
              versions={versions}
              isNarrow={isNarrow}
              onPublish={setPending}
              onEditDraft={onEditDraft}
            />
          </section>
          <RuleFileEditor
            product={expanded}
            mode={mode}
            value={draftText}
            busy={busy}
            issues={issues}
            onChange={setDraftText}
            onSubmit={() => void onSubmitDraft()}
            onCancelEdit={() => setMode({ kind: 'create' })}
          />
        </div>
      ) : null}

      {pending !== null && expanded !== null ? (
        <ConfirmDialog
          title={`Publish ${expanded} v${pending.version}?`}
          confirmLabel="Publish"
          busy={busy}
          onConfirm={() => void onConfirmPublish()}
          onCancel={() => setPending(null)}
        >
          <p>
            Publishing makes this version the active rule set for new quotes and renewals. A published
            version is immutable and cannot be edited or re-published.
          </p>
        </ConfirmDialog>
      ) : null}
    </div>
  );
}
