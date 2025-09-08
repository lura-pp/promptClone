# Database Models for AI Marketing Campaign Post Generator
# Author: JP + 2025-06-16
# Description: Pydantic models corresponding to SQLite database schema
# Purpose: Type safety, validation, and ORM-like functionality for database operations

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
import uuid


class CampaignType(str, Enum):
    """Enumeration of campaign types"""
    PRODUCT = "product"
    SERVICE = "service"
    BRAND = "brand"
    EVENT = "event"
    GENERAL = "general"


class CampaignStatus(str, Enum):
    """Enumeration of campaign statuses"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ContentType(str, Enum):
    """Enumeration of content types"""
    IDEA = "idea"
    SOCIAL_POST = "social_post"
    VIDEO_PROMPT = "video_prompt"
    HASHTAGS = "hashtags"
    SUMMARY = "summary"
    TEXT_IMAGE = "text_image"  # Added for test compatibility


class Platform(str, Enum):
    """Enumeration of social media platforms"""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    GENERAL = "general"


class FileCategory(str, Enum):
    """Enumeration of file categories"""
    IMAGE = "image"
    DOCUMENT = "document"
    CAMPAIGN_ASSET = "campaign_asset"
    OTHER = "other"


class AnalysisStatus(str, Enum):
    """Enumeration of file analysis statuses"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TemplateCategory(str, Enum):
    """Enumeration of template categories"""
    PRODUCT_LAUNCH = "product_launch"
    BRAND_AWARENESS = "brand_awareness"
    EVENT_PROMOTION = "event_promotion"
    CUSTOM = "custom"


# ============================================================================
# BASE MODELS
# ============================================================================

class BaseDBModel(BaseModel):
    """Base model with common database fields"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# USER MODELS
# ============================================================================

class UserBase(BaseModel):
    """Base user model for shared fields"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=200)  # Updated to match schema
    profile_data: Optional[Dict[str, Any]] = None


class UserCreate(UserBase):
    """Model for creating a new user"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Model for updating user information"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=200)  # Updated to match schema
    profile_data: Optional[Dict[str, Any]] = None


class User(UserBase, BaseDBModel):
    """Complete user model with database fields"""
    password_hash: Optional[str] = None  # Made optional for test compatibility
    last_login: Optional[datetime] = None
    is_active: bool = True

    @validator('profile_data', pre=True)
    def parse_profile_data(cls, v):
        """Parse JSON string to dict if needed"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class UserResponse(UserBase, BaseDBModel):
    """User model for API responses (excludes sensitive data)"""
    last_login: Optional[datetime] = None
    is_active: bool = True


# ============================================================================
# CAMPAIGN MODELS
# ============================================================================

class CampaignBase(BaseModel):
    """Base campaign model for shared fields"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None  # Added for test compatibility
    business_description: Optional[str] = None
    objective: Optional[str] = None
    objectives: Optional[str] = None  # Added for test compatibility
    campaign_type: CampaignType = CampaignType.GENERAL
    creativity_level: int = Field(5, ge=1, le=10)
    target_audience: Optional[str] = None
    
    # Business Context URLs
    business_website: Optional[str] = None
    about_page_url: Optional[str] = None
    product_service_url: Optional[str] = None
    
    # Campaign Configuration
    preferred_design: Optional[str] = None
    brand_voice: Optional[str] = None
    campaign_settings: Optional[Dict[str, Any]] = None


class CampaignCreate(CampaignBase):
    """Model for creating a new campaign"""
    pass


class CampaignUpdate(BaseModel):
    """Model for updating campaign information"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None  # Added for test compatibility
    business_description: Optional[str] = None
    objective: Optional[str] = None
    objectives: Optional[str] = None  # Added for test compatibility
    campaign_type: Optional[CampaignType] = None
    creativity_level: Optional[int] = Field(None, ge=1, le=10)
    target_audience: Optional[str] = None
    business_website: Optional[str] = None
    about_page_url: Optional[str] = None
    product_service_url: Optional[str] = None
    preferred_design: Optional[str] = None
    brand_voice: Optional[str] = None
    campaign_settings: Optional[Dict[str, Any]] = None
    status: Optional[CampaignStatus] = None


class Campaign(CampaignBase, BaseDBModel):
    """Complete campaign model with database fields"""
    user_id: str
    status: CampaignStatus = CampaignStatus.DRAFT
    completed_at: Optional[datetime] = None
    
    # AI Generated Context
    ai_summary: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None  # Added for test compatibility
    business_context: Optional[Dict[str, Any]] = None
    suggested_themes: Optional[List[str]] = None
    suggested_tags: Optional[List[str]] = None
    selected_themes: Optional[List[str]] = None
    selected_tags: Optional[List[str]] = None

    @validator('business_context', 'suggested_themes', 'suggested_tags', 'selected_themes', 'selected_tags', 'campaign_settings', 'ai_analysis', pre=True)
    def parse_json_fields(cls, v):
        """Parse JSON string fields to Python objects if needed"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class CampaignResponse(CampaignBase, BaseDBModel):
    """Campaign model for API responses"""
    user_id: str
    status: CampaignStatus
    completed_at: Optional[datetime] = None
    ai_summary: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None  # Added for test compatibility
    business_context: Optional[Dict[str, Any]] = None
    suggested_themes: Optional[List[str]] = None
    suggested_tags: Optional[List[str]] = None
    selected_themes: Optional[List[str]] = None
    selected_tags: Optional[List[str]] = None


# ============================================================================
# GENERATED CONTENT MODELS
# ============================================================================

class GeneratedContentBase(BaseModel):
    """Base generated content model for shared fields"""
    content_type: ContentType
    platform: Optional[Platform] = None
    title: Optional[str] = None
    content_text: Optional[str] = None
    content_data: Optional[Dict[str, Any]] = None
    
    # AI Generation Context
    generation_prompt: Optional[str] = None
    ai_model: Optional[str] = None
    ai_metadata: Optional[Dict[str, Any]] = None  # Added for test compatibility
    generation_parameters: Optional[Dict[str, Any]] = None
    
    # Content Metadata
    hashtags: Optional[List[str]] = None
    mentions: Optional[List[str]] = None
    media_urls: Optional[List[str]] = None
    engagement_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class GeneratedContentCreate(GeneratedContentBase):
    """Model for creating generated content"""
    campaign_id: str


class GeneratedContentUpdate(BaseModel):
    """Model for updating generated content"""
    title: Optional[str] = None
    content_text: Optional[str] = None
    content_data: Optional[Dict[str, Any]] = None
    is_selected: Optional[bool] = None
    is_published: Optional[bool] = None
    user_edits: Optional[Dict[str, Any]] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    scheduled_for: Optional[datetime] = None


class GeneratedContent(GeneratedContentBase, BaseDBModel):
    """Complete generated content model with database fields"""
    campaign_id: str
    
    # User Interaction
    is_selected: bool = False
    is_published: bool = False
    user_edits: Optional[Dict[str, Any]] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    
    # Scheduling
    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    platform_post_id: Optional[str] = None

    @validator('content_data', 'generation_parameters', 'hashtags', 'mentions', 'media_urls', 'user_edits', 'ai_metadata', pre=True)
    def parse_json_fields(cls, v):
        """Parse JSON string fields to Python objects if needed"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class GeneratedContentResponse(GeneratedContentBase, BaseDBModel):
    """Generated content model for API responses"""
    campaign_id: str
    is_selected: bool
    is_published: bool
    user_edits: Optional[Dict[str, Any]] = None
    user_rating: Optional[int] = None
    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    platform_post_id: Optional[str] = None


# ============================================================================
# UPLOADED FILE MODELS
# ============================================================================

class UploadedFileBase(BaseModel):
    """Base uploaded file model for shared fields"""
    original_filename: str
    stored_filename: str
    file_path: str
    file_size: int = Field(..., gt=0)
    mime_type: str
    file_category: FileCategory
    upload_source: Optional[str] = None


class UploadedFileCreate(UploadedFileBase):
    """Model for creating uploaded file record"""
    campaign_id: str
    user_id: str


class UploadedFileUpdate(BaseModel):
    """Model for updating uploaded file information"""
    analysis_status: Optional[AnalysisStatus] = None
    analysis_results: Optional[Dict[str, Any]] = None
    extracted_text: Optional[str] = None
    image_analysis: Optional[Dict[str, Any]] = None


class UploadedFile(UploadedFileBase, BaseDBModel):
    """Complete uploaded file model with database fields"""
    campaign_id: str
    user_id: str
    
    # File Analysis
    analysis_status: AnalysisStatus = AnalysisStatus.PENDING
    analysis_results: Optional[Dict[str, Any]] = None
    extracted_text: Optional[str] = None
    image_analysis: Optional[Dict[str, Any]] = None

    @validator('analysis_results', 'image_analysis', pre=True)
    def parse_json_fields(cls, v):
        """Parse JSON string fields to Python objects if needed"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class UploadedFileResponse(UploadedFileBase, BaseDBModel):
    """Uploaded file model for API responses"""
    campaign_id: str
    user_id: str
    analysis_status: AnalysisStatus
    analysis_results: Optional[Dict[str, Any]] = None
    extracted_text: Optional[str] = None
    image_analysis: Optional[Dict[str, Any]] = None


# ============================================================================
# CAMPAIGN TEMPLATE MODELS
# ============================================================================

class CampaignTemplateBase(BaseModel):
    """Base campaign template model for shared fields"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: TemplateCategory
    template_data: Dict[str, Any]
    default_settings: Optional[Dict[str, Any]] = None
    prompt_templates: Optional[Dict[str, Any]] = None


class CampaignTemplateCreate(CampaignTemplateBase):
    """Model for creating campaign template"""
    is_public: bool = False
    created_by: Optional[str] = None


class CampaignTemplateUpdate(BaseModel):
    """Model for updating campaign template"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    default_settings: Optional[Dict[str, Any]] = None
    prompt_templates: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class CampaignTemplate(CampaignTemplateBase, BaseDBModel):
    """Complete campaign template model with database fields"""
    usage_count: int = 0
    is_public: bool = False
    created_by: Optional[str] = None

    @validator('template_data', 'default_settings', 'prompt_templates', pre=True)
    def parse_json_fields(cls, v):
        """Parse JSON string fields to Python objects if needed"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class CampaignTemplateResponse(CampaignTemplateBase, BaseDBModel):
    """Campaign template model for API responses"""
    usage_count: int
    is_public: bool
    created_by: Optional[str] = None


# ============================================================================
# USER SESSION MODELS
# ============================================================================

class UserSessionBase(BaseModel):
    """Base user session model for shared fields"""
    session_token: str
    session_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class UserSessionCreate(UserSessionBase):
    """Model for creating user session"""
    user_id: str
    expires_at: datetime


class UserSession(UserSessionBase, BaseDBModel):
    """Complete user session model with database fields"""
    user_id: str
    expires_at: datetime
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    @validator('session_data', pre=True)
    def parse_json_fields(cls, v):
        """Parse JSON string fields to Python objects if needed"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


class UserSessionResponse(UserSessionBase, BaseDBModel):
    """User session model for API responses"""
    user_id: str
    expires_at: datetime
    last_activity: datetime
    is_active: bool


# ============================================================================
# VIEW MODELS FOR ANALYTICS
# ============================================================================

class CampaignSummary(BaseModel):
    """Campaign summary with aggregated data"""
    id: str
    name: str
    campaign_type: CampaignType
    status: CampaignStatus
    created_at: datetime
    updated_at: datetime
    username: str
    full_name: Optional[str]  # Updated to match schema
    content_count: int
    selected_content_count: int


class UserActivitySummary(BaseModel):
    """User activity summary with aggregated data"""
    id: str
    username: str
    email: str
    user_since: datetime
    last_login: Optional[datetime]
    total_campaigns: int
    active_campaigns: int
    completed_campaigns: int
    total_content_generated: int


class ContentPerformance(BaseModel):
    """Content performance metrics"""
    id: str
    campaign_id: str
    content_type: ContentType
    platform: Optional[Platform]
    title: Optional[str]
    is_selected: bool
    is_published: bool
    user_rating: Optional[int]
    engagement_score: Optional[float]
    created_at: datetime
    campaign_name: str
    username: str


# ============================================================================
# UTILITY MODELS
# ============================================================================

class DatabaseStats(BaseModel):
    """Database statistics model"""
    total_users: int
    total_campaigns: int
    total_content: int
    total_templates: int
    schema_version: str
    database_size_mb: float


class PaginatedResponse(BaseModel):
    """Generic paginated response model"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class APIResponse(BaseModel):
    """Generic API response wrapper"""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None 