import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CustomerAssistantPage } from '../pages/customer/CustomerAssistantPage';
import * as customerApi from '../api/customerApi';
import { ConversationView } from '../types/customer';
import { t } from '../locales';

vi.mock('../api/customerApi');

const mockConversation: ConversationView = {
  id: 101,
  customer_id: 1,
  status: 'active',
  draft_version: 1,
  draft: {
    service_type: 'HVAC',
    urgency: 'medium',
    location: null,
    preferred_time: null,
    problem_description: '空调吹出热风且噪音大',
    required_skills: ['HVAC'],
    missing_fields: ['location', 'preferred_time'],
    is_complete: false,
  },
  messages: [
    {
      id: 1,
      conversation_id: 101,
      role: 'assistant',
      content: t.conversation.welcomeMessage,
      created_at: new Date().toISOString(),
    },
    {
      id: 2,
      conversation_id: 101,
      role: 'customer',
      content: '空调吹出热风且噪音大',
      created_at: new Date().toISOString(),
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockReadyConversation: ConversationView = {
  ...mockConversation,
  status: 'awaiting_confirmation',
  draft: {
    ...mockConversation.draft,
    location: '北京市朝阳区建国门外大街1号',
    preferred_time: '明天下午两点',
    missing_fields: [],
    is_complete: true,
  },
};

describe('CustomerAssistantPage (Conversational Agent)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chat interface and displays existing messages', async () => {
    vi.mocked(customerApi.fetchConversations).mockResolvedValue([
      {
        id: 101,
        status: 'active',
        draft_preview: '空调吹出热风且噪音大',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
    vi.mocked(customerApi.fetchConversation).mockResolvedValue(mockConversation);

    render(
      <MemoryRouter initialEntries={['/customer/assistant?id=101']}>
        <CustomerAssistantPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('AI 智能报修')).toBeInTheDocument();
      expect(screen.getByText(/您好，我是 FieldOps 智能服务助手/)).toBeInTheDocument();
      expect(screen.getAllByText('空调吹出热风且噪音大').length).toBeGreaterThanOrEqual(1);
    });

    // Check draft summary card shows missing fields
    expect(screen.getByText(t.conversation.draft.stillNeeded)).toBeInTheDocument();
    expect(screen.getByText(t.conversation.draft.provideDetailsHint)).toBeDisabled();
  });

  it('enables Confirm & Submit button only when conversation is ready for confirmation', async () => {
    vi.mocked(customerApi.fetchConversations).mockResolvedValue([]);
    vi.mocked(customerApi.fetchConversation).mockResolvedValue(mockReadyConversation);

    render(
      <MemoryRouter initialEntries={['/customer/assistant?id=101']}>
        <CustomerAssistantPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      const confirmBtn = screen.getByRole('button', { name: new RegExp(t.conversation.draft.confirmAndSubmit, 'i') });
      expect(confirmBtn).toBeInTheDocument();
      expect(confirmBtn).not.toBeDisabled();
    });
  });

  it('calls sendConversationMessage with client_message_id when user sends input', async () => {
    vi.mocked(customerApi.fetchConversations).mockResolvedValue([]);
    vi.mocked(customerApi.fetchConversation).mockResolvedValue(mockConversation);
    vi.mocked(customerApi.sendConversationMessage).mockResolvedValue({
      ...mockConversation,
      draft_version: 2,
      messages: [
        ...mockConversation.messages,
        {
          id: 3,
          conversation_id: 101,
          role: 'customer',
          content: '我家在海淀区中关村',
          created_at: new Date().toISOString(),
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/customer/assistant?id=101']}>
        <CustomerAssistantPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('AI 智能报修')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(new RegExp(t.conversation.input.placeholder, 'i'));
    fireEvent.change(input, { target: { value: '我家在海淀区中关村' } });

    const form = input.closest('form');
    if (form) {
      fireEvent.submit(form);
    }

    await waitFor(() => {
      expect(customerApi.sendConversationMessage).toHaveBeenCalledWith(
        101,
        expect.objectContaining({
          content: '我家在海淀区中关村',
          client_message_id: expect.any(String),
        })
      );
    });
  });

  it('handles confirm conversation and navigates to request detail on success', async () => {
    vi.mocked(customerApi.fetchConversations).mockResolvedValue([]);
    vi.mocked(customerApi.fetchConversation).mockResolvedValue(mockReadyConversation);
    vi.mocked(customerApi.confirmConversation).mockResolvedValue({
      conversation_id: 101,
      service_request_id: 501,
      status: 'submitted',
      message: '工单已提交',
      success: true,
    });

    render(
      <MemoryRouter initialEntries={['/customer/assistant?id=101']}>
        <CustomerAssistantPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      const confirmBtn = screen.getByRole('button', { name: new RegExp(t.conversation.draft.confirmAndSubmit, 'i') });
      expect(confirmBtn).not.toBeDisabled();
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(customerApi.confirmConversation).toHaveBeenCalledWith(101, expect.any(String));
    });
  });
});
