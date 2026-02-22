import { useEffect, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import type { CesiumSnapshot, ConjunctionEvent } from '../types'

interface Props {
  snapshot: CesiumSnapshot | null
  timeIndex: number
  selectedEvent: ConjunctionEvent | null
  onTimeChange: (index: number) => void
  showContinents: boolean
}

export default function CesiumGlobe({ snapshot, timeIndex, selectedEvent, onTimeChange, showContinents }: Props) {
  const [selectedObjectPopup, setSelectedObjectPopup] = useState<{
    name: string
    noradId: number
    sourceGroup: string
  } | null>(null)
  const [selectedPairPopup, setSelectedPairPopup] = useState<{
    primaryName: string
    primaryId: number
    secondaryName: string
    secondaryId: number
    bothFound: boolean
    missDistanceKm: string
    pcText: string
    riskTier: string
  } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const initializedRef = useRef(false)
  const starsCollectionRef = useRef<Cesium.PointPrimitiveCollection | null>(null)
  const clickHandlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null)
  const snapshotRef = useRef<CesiumSnapshot | null>(snapshot)
  const pointPrimsRef = useRef<Cesium.PointPrimitive[]>([])
  const pointCollectionRef = useRef<Cesium.PointPrimitiveCollection | null>(null)
  const noradIndexMapRef = useRef<Map<number, number>>(new Map())
  const pulseEntityRef = useRef<Cesium.Entity | null>(null)
  const continentsRef = useRef<Cesium.GeoJsonDataSource | null>(null)

  useEffect(() => {
    snapshotRef.current = snapshot
  }, [snapshot])

  // Initialize viewer once
  useEffect(() => {
    if (initializedRef.current || !containerRef.current) return
    initializedRef.current = true
    let disposed = false

    try {
      // Suppress Ion token warning — we're not using Ion assets
      Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.stub'

      const viewer = new Cesium.Viewer(containerRef.current, {
        // v1.99+ API: baseLayer:false skips default imagery
        baseLayer: false as unknown as Cesium.ImageryLayer,
        terrainProvider: new Cesium.EllipsoidTerrainProvider(),
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
        skyBox: false as unknown as Cesium.SkyBox,
        skyAtmosphere: false as unknown as Cesium.SkyAtmosphere,
        requestRenderMode: false,
      })

      // Remove any imagery layers that snuck in
      viewer.scene.imageryLayers.removeAll()

      // Keep a dark globe for contrast, but with a calmer navy palette.
      viewer.scene.globe.baseColor = new Cesium.Color(0.08, 0.12, 0.19, 1.0)
      viewer.scene.globe.showGroundAtmosphere = false
      viewer.scene.globe.depthTestAgainstTerrain = false
      viewer.scene.fog.enabled = false
      if (viewer.scene.sun) viewer.scene.sun.show = false
      if (viewer.scene.moon) viewer.scene.moon.show = false
      viewer.scene.backgroundColor = new Cesium.Color(0.04, 0.06, 0.1, 1.0)

      // Default camera: pull back to see the whole Earth
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(0, 20, 25_000_000),
      })

      // Bloom post-processing
      try {
        const bloom = viewer.scene.postProcessStages.bloom
        bloom.enabled = true
        bloom.uniforms['glowOnly'] = false
        bloom.uniforms['contrast'] = 128
        bloom.uniforms['brightness'] = -0.3
        bloom.uniforms['delta'] = 1.0
        bloom.uniforms['sigma'] = 3.78
        bloom.uniforms['stepSize'] = 5.0
      } catch {
        // bloom not supported — skip silently
      }

      viewerRef.current = viewer

      const stars = new Cesium.PointPrimitiveCollection()
      viewer.scene.primitives.add(stars)
      starsCollectionRef.current = stars
      const starCount = 700
      for (let i = 0; i < starCount; i += 1) {
        const theta = Math.random() * Math.PI * 2
        const u = Math.random() * 2 - 1
        const radius = 70_000_000 + Math.random() * 35_000_000
        const radial = Math.sqrt(1 - u * u)
        stars.add({
          position: new Cesium.Cartesian3(
            radius * radial * Math.cos(theta),
            radius * radial * Math.sin(theta),
            radius * u
          ),
          color: new Cesium.Color(0.93, 0.97, 1.0, 0.42 + Math.random() * 0.36),
          pixelSize: Math.random() < 0.16 ? 2 : 1,
        })
      }

      const clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
      clickHandler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
        const liveSnapshot = snapshotRef.current
        if (!liveSnapshot) {
          setSelectedObjectPopup(null)
          return
        }
        const picked = viewer.scene.pick(movement.position)
        const primitive = picked && (picked as { primitive?: unknown }).primitive
        if (!primitive) {
          setSelectedObjectPopup(null)
          return
        }
        const idx = pointPrimsRef.current.indexOf(primitive as Cesium.PointPrimitive)
        if (idx < 0 || idx >= liveSnapshot.objects.length) {
          setSelectedObjectPopup(null)
          return
        }
        const obj = liveSnapshot.objects[idx]
        setSelectedObjectPopup({
          name: obj.name || `Object ${obj.norad_id}`,
          noradId: obj.norad_id,
          sourceGroup: obj.source_group,
        })
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
      clickHandlerRef.current = clickHandler

      const outlineColor = new Cesium.Color(0.58, 0.82, 0.96, 0.95)
      const fillColor = new Cesium.Color(0.43, 0.68, 0.86, 0.12)
      Cesium.GeoJsonDataSource.load('/geo/ne_110m_land.geojson', {
        clampToGround: false,
        stroke: outlineColor,
        strokeWidth: 1.8,
        fill: fillColor,
      }).then((dataSource) => {
        if (disposed || viewer.isDestroyed()) return

        continentsRef.current = dataSource
        viewer.dataSources.add(dataSource)
        dataSource.show = showContinents

        for (const entity of dataSource.entities.values) {
          if (entity.polygon) {
            entity.polygon.outline = new Cesium.ConstantProperty(true)
            entity.polygon.outlineColor = new Cesium.ConstantProperty(outlineColor)
            entity.polygon.material = new Cesium.ColorMaterialProperty(fillColor)
            entity.polygon.fill = new Cesium.ConstantProperty(true)
            entity.polygon.height = new Cesium.ConstantProperty(12000)
          }
          if (entity.label) {
            entity.label.show = new Cesium.ConstantProperty(false)
          }
        }
      }).catch((err) => {
        console.warn('Continents overlay load failed:', err)
      })
    } catch (err) {
      console.error('Cesium Viewer init failed:', err)
    }

    return () => {
      disposed = true
      continentsRef.current = null
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy()
      }
      if (clickHandlerRef.current && !clickHandlerRef.current.isDestroyed()) {
        clickHandlerRef.current.destroy()
      }
      initializedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (continentsRef.current) {
      continentsRef.current.show = showContinents
    }
  }, [showContinents])

  // Build point cloud when snapshot loads
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !snapshot) return

    // Remove previous collection
    if (pointCollectionRef.current) {
      viewer.scene.primitives.remove(pointCollectionRef.current)
    }

    const points = new Cesium.PointPrimitiveCollection()
    viewer.scene.primitives.add(points)
    pointCollectionRef.current = points

    const noradMap = new Map<number, number>()
    snapshot.objects.forEach((obj, i) => noradMap.set(obj.norad_id, i))
    noradIndexMapRef.current = noradMap

    const safeIdx = Math.min(Math.max(timeIndex, 0), snapshot.times_utc.length - 1)
    const prims = snapshot.objects.map((obj) => {
      const pos = obj.positions_ecef_m[safeIdx] ?? obj.positions_ecef_m[0]
      return points.add({
        position: new Cesium.Cartesian3(pos[0], pos[1], pos[2]),
        color: obj.source_group === 'ACTIVE'
          ? new Cesium.Color(0.42, 0.75, 0.93, 0.9)
          : new Cesium.Color(0.91, 0.63, 0.36, 0.78),
        pixelSize: 3,
        scaleByDistance: new Cesium.NearFarScalar(1.5e6, 4.0, 5.5e7, 1.0),
      })
    })
    pointPrimsRef.current = prims
  }, [snapshot]) // eslint-disable-line react-hooks/exhaustive-deps

  // Update positions on timeIndex change
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !snapshot || pointPrimsRef.current.length === 0) return

    const safeIdx = Math.min(Math.max(timeIndex, 0), snapshot.times_utc.length - 1)
    snapshot.objects.forEach((obj, i) => {
      const pos = obj.positions_ecef_m[safeIdx]
      if (pos && pointPrimsRef.current[i]) {
        pointPrimsRef.current[i].position = new Cesium.Cartesian3(pos[0], pos[1], pos[2])
      }
    })
    viewer.scene.requestRender()
  }, [timeIndex, snapshot])

  // Handle selected event
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewer.isDestroyed() || !snapshot || !selectedEvent) {
      setSelectedPairPopup(null)
      return
    }

    const noradMap = noradIndexMapRef.current
    const prims = pointPrimsRef.current

    // Jump to TCA timestep
    onTimeChange(selectedEvent.tca_index_snapshot)
    const tIdx = selectedEvent.tca_index_snapshot

    // Reset all points
    prims.forEach((p) => {
      p.pixelSize = 3.0
      p.outlineWidth = 0
    })

    const primaryIdx = noradMap.get(selectedEvent.primary_norad_id)
    const secondaryIdx = noradMap.get(selectedEvent.secondary_norad_id)
    const primaryObj = primaryIdx !== undefined ? snapshot.objects[primaryIdx] : null
    const secondaryObj = secondaryIdx !== undefined ? snapshot.objects[secondaryIdx] : null

    setSelectedPairPopup({
      primaryName: primaryObj?.name || selectedEvent.primary_name || `Object ${selectedEvent.primary_norad_id}`,
      primaryId: selectedEvent.primary_norad_id,
      secondaryName: secondaryObj?.name || selectedEvent.secondary_name || `Object ${selectedEvent.secondary_norad_id}`,
      secondaryId: selectedEvent.secondary_norad_id,
      bothFound: primaryIdx !== undefined && secondaryIdx !== undefined,
      missDistanceKm: Math.max(0, selectedEvent.miss_distance_m / 1000).toFixed(1),
      pcText: selectedEvent.pc_assumed > 0 ? `1e${Math.round(Math.log10(selectedEvent.pc_assumed))}` : '<1e-10',
      riskTier: selectedEvent.risk_tier,
    })

    if (primaryIdx !== undefined && prims[primaryIdx]) {
      prims[primaryIdx].pixelSize = 14
      prims[primaryIdx].outlineColor = new Cesium.Color(1, 0.92, 0.62, 0.95)
      prims[primaryIdx].outlineWidth = 2
    }
    if (secondaryIdx !== undefined && prims[secondaryIdx]) {
      prims[secondaryIdx].pixelSize = 12
      prims[secondaryIdx].outlineColor = new Cesium.Color(0.9, 0.96, 1, 0.95)
      prims[secondaryIdx].outlineWidth = 2
    }

    // Remove previous pulse entity
    if (pulseEntityRef.current) {
      viewer.entities.remove(pulseEntityRef.current)
      pulseEntityRef.current = null
    }
    if (primaryIdx !== undefined && secondaryIdx !== undefined) {
      const pPos = snapshot.objects[primaryIdx].positions_ecef_m[tIdx]
      const sPos = snapshot.objects[secondaryIdx].positions_ecef_m[tIdx]

      if (pPos && sPos) {
        const primaryCart = new Cesium.Cartesian3(pPos[0], pPos[1], pPos[2])
        const secondaryCart = new Cesium.Cartesian3(sPos[0], sPos[1], sPos[2])

        pulseEntityRef.current = viewer.entities.add({
          polyline: {
            positions: [primaryCart, secondaryCart],
            width: 4,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.65,
              color: new Cesium.CallbackProperty(() => {
                const alpha = 0.62 + 0.38 * Math.abs(Math.sin(Date.now() / 350))
                return new Cesium.Color(1, 0, 0, alpha)
              }, false),
            }),
          },
        })

        // Camera fly-to midpoint, 2000 km above
        const mid = Cesium.Cartesian3.midpoint(primaryCart, secondaryCart, new Cesium.Cartesian3())
        const midCarto = Cesium.Cartographic.fromCartesian(mid)
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromRadians(
            midCarto.longitude,
            midCarto.latitude,
            midCarto.height + 2_000_000
          ),
          duration: 2.0,
          easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
        })
      }
    }

    viewer.scene.requestRender()
  }, [selectedEvent]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#0f1b2c' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <div
        style={{
          position: 'absolute',
          right: 12,
          top: 12,
          padding: '10px 12px',
          borderRadius: 10,
          border: '1px solid rgba(198, 214, 238, 0.26)',
          background: 'rgba(8, 18, 31, 0.54)',
          color: '#dbe8fa',
          pointerEvents: 'none',
          minWidth: 190,
          backdropFilter: 'blur(2px)',
        }}
      >
        <div style={{ fontSize: 10, letterSpacing: '0.08em', fontWeight: 700, marginBottom: 8 }}>MAP LEGEND</div>
        <LegendItem color="#6bbfed" label="Active Satellite" />
        <LegendItem color="#e8a05c" label="Space Junk / Debris" />
        <div style={{ fontSize: 10, marginTop: 8, lineHeight: 1.35, color: 'rgba(219,232,250,0.82)' }}>
          Math model: orbital propagation from computed trajectory snapshots.
        </div>
      </div>
      {selectedPairPopup && (
        <div
          style={{
            position: 'absolute',
            left: 12,
            bottom: 12,
            padding: '11px 12px',
            borderRadius: 10,
            border: '1px solid rgba(198, 214, 238, 0.3)',
            background: 'rgba(8, 18, 31, 0.62)',
            color: '#dbe8fa',
            pointerEvents: 'none',
            minWidth: 250,
            maxWidth: 320,
          }}
        >
          <div style={{ fontSize: 10, letterSpacing: '0.08em', fontWeight: 700, marginBottom: 6 }}>
            POTENTIAL COLLISION PAIR
          </div>
          <div style={{ fontSize: 12, fontWeight: 700 }}>
            A: {selectedPairPopup.primaryName}
          </div>
          <div style={{ fontSize: 11, color: 'rgba(219,232,250,0.86)', marginTop: 1 }}>
            NORAD {selectedPairPopup.primaryId}
          </div>
          <div style={{ fontSize: 12, fontWeight: 700, marginTop: 6 }}>
            B: {selectedPairPopup.secondaryName}
          </div>
          <div style={{ fontSize: 11, color: 'rgba(219,232,250,0.86)', marginTop: 1 }}>
            NORAD {selectedPairPopup.secondaryId}
          </div>
          <div style={{ fontSize: 10, marginTop: 6, lineHeight: 1.4, color: 'rgba(219,232,250,0.84)' }}>
            Dist {selectedPairPopup.missDistanceKm} km
            {' · '}
            Pc {selectedPairPopup.pcText}
            {' · '}
            {selectedPairPopup.riskTier}
          </div>
          {!selectedPairPopup.bothFound && (
            <div style={{ fontSize: 10, marginTop: 6, color: 'rgba(255, 196, 108, 0.95)' }}>
              One object is missing from the current snapshot view.
            </div>
          )}
        </div>
      )}
      {selectedObjectPopup && (
        <div
          style={{
            position: 'absolute',
            left: 12,
            top: 12,
            padding: '10px 12px',
            borderRadius: 10,
            border: '1px solid rgba(198, 214, 238, 0.28)',
            background: 'rgba(8, 18, 31, 0.58)',
            color: '#dbe8fa',
            minWidth: 220,
            maxWidth: 280,
          }}
        >
          <div style={{ fontSize: 10, letterSpacing: '0.08em', fontWeight: 700, marginBottom: 6 }}>
            OBJECT DETAILS
          </div>
          <div style={{ fontSize: 12, fontWeight: 700 }}>{selectedObjectPopup.name}</div>
          <div style={{ fontSize: 11, marginTop: 2, color: 'rgba(219,232,250,0.86)' }}>
            NORAD {selectedObjectPopup.noradId}
          </div>
          <div style={{ fontSize: 10, marginTop: 4, color: 'rgba(219,232,250,0.82)' }}>
            Group: {selectedObjectPopup.sourceGroup}
          </div>
        </div>
      )}
      {!snapshot && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'rgba(186, 206, 231, 0.72)', fontSize: 12, letterSpacing: '0.08em',
          pointerEvents: 'none',
        }}>
          LOADING ORBIT DATA...
        </div>
      )}
    </div>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: '50%',
          background: color,
          border: '1px solid rgba(255,255,255,0.3)',
          flexShrink: 0,
        }}
      />
      <span style={{ fontSize: 11, lineHeight: 1.25 }}>{label}</span>
    </div>
  )
}
