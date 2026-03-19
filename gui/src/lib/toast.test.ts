import { describe, it, expect, beforeEach } from 'vitest';
import { showToast } from './toast';

beforeEach(() => {
  document.body.innerHTML = '<div class="toast-container toast-bottom-right"></div>';
});

describe('showToast — HTML escaping', () => {
  it('escapes HTML in message to prevent XSS', () => {
    showToast('<img src=x onerror=alert(1)>', 'danger', 0);

    const msg = document.querySelector('.toast-message');
    expect(msg).not.toBeNull();
    // Should contain escaped text, not a real <img> element
    expect(msg!.innerHTML).not.toContain('<img');
    expect(msg!.innerHTML).toContain('&lt;img');
    expect(msg!.textContent).toBe('<img src=x onerror=alert(1)>');
  });

  it('escapes ampersands', () => {
    showToast('A & B', 'info', 0);

    const msg = document.querySelector('.toast-message');
    expect(msg!.innerHTML).toContain('&amp;');
    expect(msg!.textContent).toBe('A & B');
  });

  it('renders plain text messages unchanged', () => {
    showToast('3 files renamed successfully', 'success', 0);

    const msg = document.querySelector('.toast-message');
    expect(msg!.textContent).toBe('3 files renamed successfully');
  });
});
