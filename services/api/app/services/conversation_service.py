"""Conversation management service"""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from ..models.conversation import ConversationV2, ConversationMessage, ConversationShare


class ConversationService:
    """对话管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Conversation CRUD ====================
    
    def create_conversation(
        self,
        user_id: str,
        title: str = None,
        scenario_id: str = None
    ) -> ConversationV2:
        """创建新对话"""
        conversation = ConversationV2(
            conversation_id=str(uuid.uuid4()),
            user_id=user_id,
            title=title or "新对话",
            scenario_id=scenario_id,
            status="active",
            is_pinned=False,
            message_count=0,
            tags=[],
            conv_metadata={}
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def get_conversation(self, conversation_id: str, user_id: str = None) -> Optional[ConversationV2]:
        """获取对话详情"""
        query = self.db.query(ConversationV2).filter(
            ConversationV2.conversation_id == conversation_id
        )
        if user_id:
            query = query.filter(ConversationV2.user_id == user_id)
        return query.first()
    
    def get_conversation_by_id(self, id: int) -> Optional[ConversationV2]:
        """通过数据库 ID 获取对话"""
        return self.db.query(ConversationV2).filter(ConversationV2.id == id).first()
    
    def list_conversations(
        self,
        user_id: str,
        status: str = "active",
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[ConversationV2]:
        """获取用户的对话列表"""
        query = self.db.query(ConversationV2).filter(
            ConversationV2.user_id == user_id
        )
        
        if not include_archived:
            query = query.filter(ConversationV2.status == status)
        else:
            query = query.filter(ConversationV2.status.in_(["active", "archived"]))
        
        # 置顶的排在前面，然后按更新时间降序
        query = query.order_by(
            desc(ConversationV2.is_pinned),
            desc(ConversationV2.updated_at)
        )
        
        return query.offset(offset).limit(limit).all()
    
    def list_conversations_grouped(self, user_id: str) -> Dict[str, List[ConversationV2]]:
        """获取分组的对话列表（今天/昨天/本周/更早）"""
        conversations = self.list_conversations(user_id, limit=100)
        
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)
        
        groups = {
            "pinned": [],
            "today": [],
            "yesterday": [],
            "this_week": [],
            "earlier": []
        }
        
        for conv in conversations:
            updated = conv.updated_at or conv.started_at
            if updated:
                updated = updated.replace(tzinfo=timezone.utc) if updated.tzinfo is None else updated
            
            if conv.is_pinned:
                groups["pinned"].append(conv)
            elif updated and updated >= today_start:
                groups["today"].append(conv)
            elif updated and updated >= yesterday_start:
                groups["yesterday"].append(conv)
            elif updated and updated >= week_start:
                groups["this_week"].append(conv)
            else:
                groups["earlier"].append(conv)
        
        return groups
    
    def update_conversation(
        self,
        conversation_id: str,
        user_id: str,
        title: str = None,
        tags: List[str] = None,
        scenario_id: str = None
    ) -> Optional[ConversationV2]:
        """更新对话"""
        conv = self.get_conversation(conversation_id, user_id)
        if not conv:
            return None
        
        if title is not None:
            conv.title = title
        if tags is not None:
            conv.tags = tags
        if scenario_id is not None:
            conv.scenario_id = scenario_id
        
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """删除对话（软删除）"""
        conv = self.get_conversation(conversation_id, user_id)
        if not conv:
            return False
        
        conv.status = "deleted"
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True
    
    def archive_conversation(self, conversation_id: str, user_id: str) -> Optional[ConversationV2]:
        """归档对话"""
        conv = self.get_conversation(conversation_id, user_id)
        if not conv:
            return None
        
        conv.status = "archived"
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv
    
    def unarchive_conversation(self, conversation_id: str, user_id: str) -> Optional[ConversationV2]:
        """取消归档"""
        conv = self.get_conversation(conversation_id, user_id)
        if not conv:
            return None
        
        conv.status = "active"
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv
    
    def pin_conversation(self, conversation_id: str, user_id: str, pinned: bool = True) -> Optional[ConversationV2]:
        """置顶/取消置顶"""
        conv = self.get_conversation(conversation_id, user_id)
        if not conv:
            return None
        
        conv.is_pinned = pinned
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv
    
    def search_conversations(self, user_id: str, query: str, limit: int = 20) -> List[ConversationV2]:
        """搜索对话"""
        # 搜索标题和摘要
        search_pattern = f"%{query}%"
        results = self.db.query(ConversationV2).filter(
            ConversationV2.user_id == user_id,
            ConversationV2.status != "deleted",
            or_(
                ConversationV2.title.ilike(search_pattern),
                ConversationV2.summary.ilike(search_pattern)
            )
        ).order_by(desc(ConversationV2.updated_at)).limit(limit).all()
        
        return results
    
    # ==================== Message Operations ====================
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        retrieved_context: Dict = None,
        sources: List = None,
        tokens_used: int = None,
        model_used: str = None,
        latency_ms: int = None
    ) -> ConversationMessage:
        """添加消息"""
        message = ConversationMessage(
            conversation_id=conversation_id,
            message_id=str(uuid.uuid4()),
            role=role,
            content=content,
            retrieved_context=retrieved_context,
            sources=sources or [],
            tokens_used=tokens_used,
            model_used=model_used,
            latency_ms=latency_ms,
            msg_metadata={}
        )
        self.db.add(message)
        
        # 更新对话统计
        conv = self.db.query(ConversationV2).filter(
            ConversationV2.conversation_id == conversation_id
        ).first()
        if conv:
            conv.message_count = (conv.message_count or 0) + 1
            conv.last_message_at = datetime.now(timezone.utc)
            conv.updated_at = datetime.now(timezone.utc)
            
            # 如果是第一条用户消息，自动生成标题
            if conv.message_count == 1 and role == "user":
                conv.title = content[:50] + ("..." if len(content) > 50 else "")
        
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def get_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        order_asc: bool = True
    ) -> List[ConversationMessage]:
        """获取对话消息列表"""
        query = self.db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        )
        
        if order_asc:
            query = query.order_by(ConversationMessage.created_at.asc())
        else:
            query = query.order_by(ConversationMessage.created_at.desc())
        
        return query.offset(offset).limit(limit).all()
    
    def update_message_feedback(
        self,
        message_id: str,
        feedback: str,
        feedback_text: str = None
    ) -> Optional[ConversationMessage]:
        """更新消息反馈"""
        message = self.db.query(ConversationMessage).filter(
            ConversationMessage.message_id == message_id
        ).first()
        
        if not message:
            return None
        
        message.feedback = feedback
        message.feedback_text = feedback_text
        self.db.commit()
        self.db.refresh(message)
        return message
    
    # ==================== Share Operations ====================
    
    def create_share(
        self,
        conversation_id: str,
        user_id: int,
        allow_copy: bool = True,
        expires_in_days: int = None
    ) -> ConversationShare:
        """创建分享链接"""
        share = ConversationShare(
            conversation_id=conversation_id,
            share_token=secrets.token_urlsafe(32),
            shared_by=user_id,
            allow_copy=allow_copy,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days) if expires_in_days else None,
            view_count=0
        )
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share
    
    def get_share_by_token(self, token: str) -> Optional[ConversationShare]:
        """通过 token 获取分享"""
        share = self.db.query(ConversationShare).filter(
            ConversationShare.share_token == token
        ).first()
        
        if share and not share.is_expired:
            # 增加浏览次数
            share.view_count = (share.view_count or 0) + 1
            self.db.commit()
            return share
        
        return None
    
    def delete_share(self, conversation_id: str, user_id: int) -> bool:
        """删除分享"""
        share = self.db.query(ConversationShare).filter(
            ConversationShare.conversation_id == conversation_id,
            ConversationShare.shared_by == user_id
        ).first()
        
        if share:
            self.db.delete(share)
            self.db.commit()
            return True
        
        return False
    
    def get_shared_conversation(self, token: str) -> Optional[Dict[str, Any]]:
        """获取分享的对话内容"""
        share = self.get_share_by_token(token)
        if not share:
            return None
        
        conv = self.db.query(ConversationV2).filter(
            ConversationV2.conversation_id == share.conversation_id
        ).first()
        
        if not conv:
            return None
        
        messages = self.get_messages(share.conversation_id)
        
        return {
            "conversation": conv.to_dict(),
            "messages": [m.to_dict() for m in messages],
            "allow_copy": share.allow_copy,
            "shared_at": share.created_at.isoformat() if share.created_at else None
        }

