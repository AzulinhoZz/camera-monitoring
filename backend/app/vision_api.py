"""Authenticated configuration only; there is deliberately no public ingest API."""
import os
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ValidationError
from supabase import create_client

from .auth import get_current_user
from .permissions import has_camera_access, can_manage_camera
from .vision.contracts import Contract, CameraScope
from .vision.rules import Rule, RuleEngine

router = APIRouter(prefix='/cameras', tags=['Vision rules'])


class ConfigUpdate(Contract):
    revision: int = Field(ge=0, le=2**63-2)
    rules: list[dict] = Field(max_length=32)


def get_client():
    return create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])


def camera_scope(client, camera_id):
    rows = client.table('cameras').select('id,user_id,organization_id').eq('id',str(camera_id)).execute().data or []
    if len(rows)!=1:
        raise HTTPException(404,'Cámara no encontrada')
    return CameraScope(camera_id=rows[0]['id'],owner_id=rows[0]['user_id'],organization_id=rows[0].get('organization_id'))


def read_config(client, scope):
    rows=client.table('camera_vision_configs').select('revision,rules,owner_id,organization_id').eq('camera_id',str(scope.camera_id)).execute().data or []
    if not rows:
        return {'revision':0,'rules':[]}
    row=rows[0]
    # Preserve revision for optimistic write after a transfer, but hide old rules.
    matches=str(scope.owner_id)==str(row['owner_id']) and (str(scope.organization_id) if scope.organization_id else None)==row.get('organization_id')
    return {'revision':row['revision'],'rules':row['rules'] if matches else []}


def failure(exc):
    code=getattr(exc,'code',None)
    return HTTPException(409 if code=='40001' else 403 if code=='42501' else 503,
                         'Configuración modificada; recarga antes de guardar' if code=='40001' else 'No se pudo acceder a las reglas de visión')


@router.get('/{camera_id}/vision-rules')
def list_rules(camera_id: UUID, user:dict=Depends(get_current_user)):
    if not has_camera_access(user,str(camera_id)):
        raise HTTPException(403,'Sin acceso a esta cámara')
    try:
        client=get_client()
        scope=camera_scope(client,camera_id)
        config=read_config(client,scope)
        return {**config,'can_manage':can_manage_camera(user,str(camera_id))}
    except HTTPException: raise
    except Exception as exc: raise failure(exc) from None


@router.put('/{camera_id}/vision-rules')
def replace_rules(camera_id: UUID, payload:ConfigUpdate, user:dict=Depends(get_current_user)):
    if not can_manage_camera(user,str(camera_id)):
        raise HTTPException(403,'Solo el propietario o administrador puede editar reglas')
    try:
        client=get_client()
        scope=camera_scope(client,camera_id)
        rules=[]
        for item in payload.rules:
            if any(key in item for key in CameraScope.model_fields):
                raise HTTPException(422,'El ámbito de la regla lo determina el servidor')
            rules.append(Rule(**scope.model_dump(),**item))
        RuleEngine(scope,rules)
        serialized=[r.model_dump(mode='json') for r in rules]
        if len(json.dumps(serialized).encode('utf-8'))>60000:
            raise HTTPException(422,'La configuración excede el límite de tamaño')
        result=client.rpc('save_vision_config',{'p_actor_id':user['id'],'p_camera_id':str(camera_id),
            'p_revision':payload.revision,'p_rules':serialized}).execute()
        row=result.data[0]
        return {'revision':row['revision'],'rules':row['rules'],'can_manage':True}
    except ValidationError: raise HTTPException(422,'Regla inválida: comprueba geometría, clases y horario') from None
    except HTTPException: raise
    except Exception as exc: raise failure(exc) from None
