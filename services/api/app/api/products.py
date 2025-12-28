"""
产品管理 API
管理产品维度的 KU 和关联关系
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from ..db import get_db
from ..models import Product, KnowledgeUnit, KURelation
from ..services.retrieval import get_product_kus, search_with_relations

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/products", tags=["products"])


class ProductCreate(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = None
    description: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    primary_ku_id: Optional[int] = None


class ProductResponse(BaseModel):
    id: int
    product_id: str
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    primary_ku_id: Optional[int] = None
    ku_count: int = 0


class SetPrimaryRequest(BaseModel):
    ku_id: int


@router.get("", response_model=List[ProductResponse])
async def list_products(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    """获取产品列表"""
    try:
        from sqlalchemy import func
        
        query = db.query(Product)
        if category:
            query = query.filter(Product.category == category)
        
        products = query.order_by(Product.name).limit(limit).all()
        
        # 获取每个产品的 KU 数量
        result = []
        for p in products:
            ku_count = db.query(func.count(KnowledgeUnit.id)).filter(
                KnowledgeUnit.product_id == p.product_id
            ).scalar() or 0
            
            result.append(ProductResponse(
                id=p.id,
                product_id=p.product_id,
                name=p.name,
                category=p.category,
                description=p.description,
                primary_ku_id=p.primary_ku_id,
                ku_count=ku_count,
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"List products error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    db=Depends(get_db),
):
    """创建产品"""
    try:
        # 检查是否已存在
        existing = db.query(Product).filter(
            Product.product_id == product.product_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"Product {product.product_id} already exists")
        
        new_product = Product(
            product_id=product.product_id,
            name=product.name,
            category=product.category,
            description=product.description,
        )
        
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        
        return ProductResponse(
            id=new_product.id,
            product_id=new_product.product_id,
            name=new_product.name,
            category=new_product.category,
            description=new_product.description,
            primary_ku_id=new_product.primary_ku_id,
            ku_count=0,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create product error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    db=Depends(get_db),
):
    """获取产品详情"""
    try:
        product = db.query(Product).filter(
            Product.product_id == product_id
        ).first()
        
        if not product:
            # 尝试从 KU 中自动发现产品
            kus = db.query(KnowledgeUnit).filter(
                KnowledgeUnit.product_id == product_id
            ).all()
            
            if not kus:
                raise HTTPException(status_code=404, detail="Product not found")
            
            return {
                "product_id": product_id,
                "name": product_id,  # 使用 ID 作为名称
                "category": None,
                "description": None,
                "primary_ku_id": None,
                "ku_count": len(kus),
                "auto_discovered": True,
            }
        
        from sqlalchemy import func
        ku_count = db.query(func.count(KnowledgeUnit.id)).filter(
            KnowledgeUnit.product_id == product_id
        ).scalar() or 0
        
        return {
            "id": product.id,
            "product_id": product.product_id,
            "name": product.name,
            "category": product.category,
            "description": product.description,
            "primary_ku_id": product.primary_ku_id,
            "ku_count": ku_count,
            "metadata": product.metadata if hasattr(product, 'metadata') else {},
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get product error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}/kus")
async def get_product_kus_endpoint(
    product_id: str,
    include_types: Optional[str] = Query(None, description="Comma-separated KU types"),
    limit: int = Query(20, ge=1, le=100),
):
    """获取产品的所有 KU"""
    try:
        types = include_types.split(",") if include_types else None
        result = get_product_kus(product_id, include_types=types, top_k=limit)
        return result
    except Exception as e:
        logger.error(f"Get product KUs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{product_id}/primary")
async def set_primary_ku(
    product_id: str,
    request: SetPrimaryRequest,
    db=Depends(get_db),
):
    """设置产品的主 KU"""
    try:
        # 验证 KU 存在且属于该产品
        ku = db.query(KnowledgeUnit).filter(
            KnowledgeUnit.id == request.ku_id
        ).first()
        
        if not ku:
            raise HTTPException(status_code=404, detail="KU not found")
        
        if ku.product_id != product_id:
            raise HTTPException(status_code=400, detail="KU does not belong to this product")
        
        # 清除旧的主 KU 标记
        db.query(KnowledgeUnit).filter(
            KnowledgeUnit.product_id == product_id,
            KnowledgeUnit.is_primary == True
        ).update({"is_primary": False})
        
        # 设置新的主 KU
        ku.is_primary = True
        
        # 更新 Product 表
        product = db.query(Product).filter(
            Product.product_id == product_id
        ).first()
        
        if product:
            product.primary_ku_id = request.ku_id
        else:
            # 自动创建产品记录
            new_product = Product(
                product_id=product_id,
                name=ku.title,
                primary_ku_id=request.ku_id,
            )
            db.add(new_product)
        
        db.commit()
        
        return {
            "success": True,
            "product_id": product_id,
            "primary_ku_id": request.ku_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set primary KU error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{product_id}")
async def update_product(
    product_id: str,
    update: ProductUpdate,
    db=Depends(get_db),
):
    """更新产品信息"""
    try:
        product = db.query(Product).filter(
            Product.product_id == product_id
        ).first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        if update.name is not None:
            product.name = update.name
        if update.category is not None:
            product.category = update.category
        if update.description is not None:
            product.description = update.description
        if update.primary_ku_id is not None:
            product.primary_ku_id = update.primary_ku_id
        
        db.commit()
        
        return {
            "success": True,
            "product_id": product_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update product error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{product_id}/relations")
async def get_product_relations(
    product_id: str,
    db=Depends(get_db),
):
    """获取产品 KU 之间的关联关系"""
    try:
        # 获取产品的所有 KU
        kus = db.query(KnowledgeUnit).filter(
            KnowledgeUnit.product_id == product_id
        ).all()
        
        ku_ids = [str(ku.id) for ku in kus]
        
        if not ku_ids:
            return {"product_id": product_id, "relations": []}
        
        # 获取这些 KU 之间的关系
        relations = db.query(KURelation).filter(
            KURelation.source_ku_id.in_(ku_ids) | KURelation.target_ku_id.in_(ku_ids)
        ).all()
        
        return {
            "product_id": product_id,
            "ku_count": len(ku_ids),
            "relations": [
                {
                    "id": r.id,
                    "source_ku_id": r.source_ku_id,
                    "target_ku_id": r.target_ku_id,
                    "relation_type": r.relation_type,
                    "metadata": r.metadata if r.metadata else {},
                }
                for r in relations
            ],
        }
        
    except Exception as e:
        logger.error(f"Get product relations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories/list")
async def list_categories(db=Depends(get_db)):
    """获取所有产品分类"""
    try:
        from sqlalchemy import distinct
        
        categories = db.query(distinct(Product.category)).filter(
            Product.category.isnot(None)
        ).all()
        
        return {
            "categories": [c[0] for c in categories if c[0]],
        }
        
    except Exception as e:
        logger.error(f"List categories error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

