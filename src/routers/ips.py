from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.database import db
from src.dependencies import require_admin
from src.schemas import IpCreate, IpResponse, IpUpdate

router = APIRouter(prefix="/ips", tags=["IPs autorizados"])


def _serializar_ip(ip_autorizado) -> IpResponse:
    return IpResponse(
        id=ip_autorizado.id,
        ip=ip_autorizado.ip,
        descricao=ip_autorizado.descricao,
        ativo=ip_autorizado.ativo,
        criadoEm=ip_autorizado.criadoEm,
    )


@router.post("", response_model=IpResponse, status_code=status.HTTP_201_CREATED)
async def criar_ip(payload: IpCreate, _=Depends(require_admin)):
    ip = payload.ip.strip()

    if not ip:
        raise HTTPException(status_code=422, detail="IP é obrigatório")

    novo_ip = await db.ipautorizado.create(
        data={
            "ip": ip,
            "descricao": payload.descricao,
        }
    )

    return _serializar_ip(novo_ip)


@router.get("", response_model=list[IpResponse])
async def listar_ips(
    ativo: bool | None = Query(default=None),
    _=Depends(require_admin),
):
    where = {}

    if ativo is not None:
        where["ativo"] = ativo

    ips = await db.ipautorizado.find_many(
        where=where,
        order={"criadoEm": "desc"},
    )

    return [_serializar_ip(item) for item in ips]


@router.put("/{ip_id}", response_model=IpResponse)
async def editar_ip(
    ip_id: str,
    payload: IpUpdate,
    _=Depends(require_admin),
):
    ip_existente = await db.ipautorizado.find_unique(where={"id": ip_id})

    if not ip_existente:
        raise HTTPException(status_code=404, detail="IP autorizado não encontrado")

    data = payload.model_dump(exclude_unset=True)

    if "ip" in data and data["ip"] is not None:
        data["ip"] = data["ip"].strip()

        if not data["ip"]:
            raise HTTPException(status_code=422, detail="IP é obrigatório")

    ip_atualizado = await db.ipautorizado.update(
        where={"id": ip_id},
        data=data,
    )

    return _serializar_ip(ip_atualizado)


@router.patch("/{ip_id}/toggle", response_model=IpResponse)
async def toggle_ip(
    ip_id: str,
    _=Depends(require_admin),
):
    ip_existente = await db.ipautorizado.find_unique(where={"id": ip_id})

    if not ip_existente:
        raise HTTPException(status_code=404, detail="IP autorizado não encontrado")

    ip_atualizado = await db.ipautorizado.update(
        where={"id": ip_id},
        data={
            "ativo": not ip_existente.ativo,
        },
    )

    return _serializar_ip(ip_atualizado)