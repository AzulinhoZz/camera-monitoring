-- Migration: Create user_device_tokens table in Supabase
-- Description: Stores FCM device tokens per user for sending push notifications

CREATE TABLE IF NOT EXISTS public.user_device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    fcm_token TEXT NOT NULL UNIQUE,
    device_type TEXT NOT NULL DEFAULT 'android',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast user_id token lookups
CREATE INDEX IF NOT EXISTS idx_user_device_tokens_user_id ON public.user_device_tokens(user_id);

-- Trigger to update updated_at timestamp
DROP TRIGGER IF EXISTS set_user_device_tokens_updated_at ON public.user_device_tokens;
CREATE TRIGGER set_user_device_tokens_updated_at
BEFORE UPDATE ON public.user_device_tokens
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE public.user_device_tokens ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_device_tokens
DROP POLICY IF EXISTS "Users can view own device tokens" ON public.user_device_tokens;
CREATE POLICY "Users can view own device tokens"
ON public.user_device_tokens FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own device tokens" ON public.user_device_tokens;
CREATE POLICY "Users can insert own device tokens"
ON public.user_device_tokens FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own device tokens" ON public.user_device_tokens;
CREATE POLICY "Users can update own device tokens"
ON public.user_device_tokens FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own device tokens" ON public.user_device_tokens;
CREATE POLICY "Users can delete own device tokens"
ON public.user_device_tokens FOR DELETE
USING (auth.uid() = user_id);
