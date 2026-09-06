/**
 * Defensive monkey-patch for DOM Node.prototype.removeChild and Node.prototype.insertBefore.
 *
 * Root Cause:
 * When browsers (Chrome, Edge) or translation extensions (Google Translate, Edge Translate, Grammarly)
 * automatically translate web pages, they mutate the DOM by wrapping text nodes in `<font>` tags
 * or moving child elements.
 *
 * When React attempts to unmount or re-render a component during state updates (e.g. tab switches,
 * polling refreshes, notifications), it calls `parent.removeChild(child)` or `parent.insertBefore(newNode, refNode)`.
 * Since the DOM was altered outside of React, `child.parentNode !== parent`, causing the native browser error:
 * "NotFoundError: Failed to execute 'removeChild' on 'Node': The node to be removed is not a child of this node."
 * (中文: 无法对“Node”执行“removeChild”操作：要删除的节点不是此节点的子节点。)
 *
 * Resolution:
 * We intercept `removeChild` and `insertBefore`. If the child's actual `parentNode` is not `this`,
 * we safely delegate the removal to `child.parentNode` (or no-op) rather than crashing the React application tree.
 */
export function applyDomPatch(): void {
  if (typeof window === 'undefined' || typeof Node === 'undefined') {
    return;
  }

  const originalRemoveChild = Node.prototype.removeChild;
  Node.prototype.removeChild = function <T extends Node>(child: T): T {
    if (child.parentNode !== this) {
      if (process.env.NODE_ENV !== 'production') {
        console.warn(
          '[DOM Patch] Prevented NotFoundError in removeChild caused by external DOM manipulation (e.g. Google Translate).',
          { parent: this, child, actualParent: child.parentNode }
        );
      }
      if (child.parentNode) {
        return child.parentNode.removeChild(child) as T;
      }
      return child;
    }
    return originalRemoveChild.call(this, child) as T;
  };

  const originalInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function <T extends Node>(newNode: T, referenceNode: Node | null): T {
    if (referenceNode && referenceNode.parentNode !== this) {
      if (process.env.NODE_ENV !== 'production') {
        console.warn(
          '[DOM Patch] Prevented NotFoundError in insertBefore caused by external DOM manipulation (e.g. Google Translate).',
          { parent: this, referenceNode, actualParent: referenceNode.parentNode }
        );
      }
      if (referenceNode.parentNode) {
        return referenceNode.parentNode.insertBefore(newNode, referenceNode) as T;
      }
      return originalInsertBefore.call(this, newNode, null) as T;
    }
    return originalInsertBefore.call(this, newNode, referenceNode) as T;
  };
}
