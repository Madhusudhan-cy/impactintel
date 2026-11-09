import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useOutletContext } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { graphApi } from '../api/graph';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  Network,
  Search,
  Filter,
  Layers,
  ChevronRight,
  X,
  RotateCcw,
} from 'lucide-react';

function CustomCodeNode({ data }) {
  const isCenter = data.isCenter;

  const typeConfig = {
    Function: {
      border: 'border-[#16B89A]',
      badge: 'bg-[#DDF7EF] text-[#087F70]',
    },
    Component: {
      border: 'border-[#55BDEB]',
      badge: 'bg-[#E2F4FC] text-[#258FC7]',
    },
    ApiRoute: {
      border: 'border-[#087F70]',
      badge: 'bg-[#DDF7EF] text-[#087F70]',
    },
    Class: {
      border: 'border-[#258FC7]',
      badge: 'bg-[#E2F4FC] text-[#258FC7]',
    },
    File: {
      border: 'border-[#CBEAE7]',
      badge: 'bg-[#F5FAFA] text-[#6B818B]',
    },
    Test: {
      border: 'border-rose-300',
      badge: 'bg-rose-50 text-rose-700',
    },
  };

  const currentConfig = typeConfig[data.nodeType] || {
    border: 'border-[#E1ECEE]',
    badge: 'bg-[#F5FAFA] text-[#6B818B]',
  };

  return (
    <div
      className={`px-3 py-2 rounded-xl bg-white border-2 shadow-sm min-w-[180px] max-w-[260px] transition-all hover:shadow-card cursor-pointer ${
        currentConfig.border
      } ${
        isCenter
          ? 'ring-3 ring-[#16B89A]/50 ring-offset-2 ring-offset-white scale-105 shadow-aqua-glow'
          : ''
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="w-2.5 h-2.5 !bg-[#16B89A] !border-2 !border-white"
      />

      <div className="flex items-center justify-between gap-2 mb-1">
        <span
          className={`text-[9px] font-mono uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${currentConfig.badge}`}
        >
          {data.nodeType || 'Symbol'}
        </span>
        {isCenter && (
          <span className="text-[9px] px-1.5 py-0.2 rounded bg-[#087F70] text-white font-mono font-bold">
            CENTER
          </span>
        )}
      </div>

      <div className="font-mono text-xs font-bold text-[#172B35] truncate" title={data.label}>
        {data.label}
      </div>

      <div className="text-[10px] text-[#6B818B] font-mono truncate mt-0.5" title={data.path}>
        {data.path}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="w-2.5 h-2.5 !bg-[#55BDEB] !border-2 !border-white"
      />
    </div>
  );
}

const nodeTypes = {
  custom: CustomCodeNode,
};

export default function GraphExplorerPage() {
  const { repoId } = useParams();
  const outletCtx = useOutletContext();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedNodeDetails, setSelectedNodeDetails] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadSubgraph = useCallback(
    async (centerId = null) => {
      setIsLoading(true);
      try {
        const data = await graphApi.getNeighbors(owner, repo, centerId, 25);
        if (data && data.nodes) {
          const styledEdges = (data.edges || []).map((e) => ({
            ...e,
            style: { stroke: '#55BDEB', strokeWidth: 1.6 },
            labelStyle: { fill: '#087F70', fontSize: 10, fontFamily: 'monospace' },
          }));
          setNodes(data.nodes);
          setEdges(styledEdges);
          if (data.center_node_id) {
            setSelectedNodeId(data.center_node_id);
          }
        }
      } catch (err) {
        console.error('Failed to load subgraph:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [owner, repo, setNodes, setEdges]
  );

  useEffect(() => {
    loadSubgraph();
  }, [loadSubgraph]);

  useEffect(() => {
    if (!selectedNodeId) {
      setSelectedNodeDetails(null);
      return;
    }
    async function fetchDetails() {
      try {
        const details = await graphApi.getNodeDetails(owner, repo, selectedNodeId);
        setSelectedNodeDetails(details);
      } catch (err) {
        console.error('Failed to fetch node details:', err);
      }
    }
    fetchDetails();
  }, [owner, repo, selectedNodeId]);

  const handleSearch = async (val) => {
    setSearchQuery(val);
    if (!val || val.length < 2) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await graphApi.searchNodes(owner, repo, { q: val, limit: 8 });
      setSearchResults(res.nodes || []);
    } catch (err) {
      console.warn('Search failed:', err);
    }
  };

  const onNodeClick = (_, node) => {
    setSelectedNodeId(node.id);
  };

  const handleExpandNode = (nodeId) => {
    loadSubgraph(nodeId);
    setSearchResults([]);
    setSearchQuery('');
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden bg-[#F5FAFA]">
      <Header
        title="Knowledge Graph Explorer"
        subtitle={decodedRepo}
        breadcrumbs={['Repositories', decodedRepo, 'Knowledge Graph']}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <div className="flex-1 relative bg-[#F5FAFA] flex overflow-hidden">
        {/* Search & Controls Overlay */}
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2">
          <div className="relative w-64 sm:w-72">
            <Search className="w-4 h-4 text-[#6B818B] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search symbols..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-white/95 backdrop-blur-md border border-[#E1ECEE] text-xs text-[#172B35] placeholder-[#6B818B] shadow-sm focus:outline-none focus:border-[#16B89A]"
            />

            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 rounded-lg bg-white border border-[#E1ECEE] shadow-card-hover overflow-hidden divide-y divide-[#E1ECEE] z-30 max-h-56 overflow-y-auto">
                {searchResults.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleExpandNode(item.id)}
                    className="w-full p-2 text-left hover:bg-[#DDF7EF]/50 flex items-center justify-between text-xs transition-colors cursor-pointer"
                  >
                    <div className="min-w-0 pr-2">
                      <div className="font-mono font-bold text-[#172B35] truncate">{item.name}</div>
                      <div className="text-[10px] text-[#6B818B] font-mono truncate">{item.path}</div>
                    </div>
                    <Badge variant="neutral">{item.type}</Badge>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => loadSubgraph()}
            className="p-2 rounded-lg bg-white border border-[#E1ECEE] text-[#6B818B] hover:text-[#087F70] hover:border-[#16B89A] shadow-sm transition-colors cursor-pointer"
            title="Reset center"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Legend Overlay */}
        <div className="hidden sm:block absolute bottom-3 left-3 z-20 bg-white/95 backdrop-blur-md border border-[#E1ECEE] shadow-sm rounded-lg p-2.5 text-[10px] font-mono text-[#6B818B] space-y-1">
          <div className="font-bold text-[#172B35] text-[9px] uppercase mb-0.5">Entity Types</div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#16B89A]"></span>
            <span>Function / Method</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#55BDEB]"></span>
            <span>React Component</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#087F70]"></span>
            <span>API Route Handler</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-[#258FC7]"></span>
            <span>Class</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-rose-400"></span>
            <span>Test Case</span>
          </div>
        </div>

        {/* React Flow Canvas */}
        <div className="flex-1 h-full">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            attributionPosition="bottom-left"
          >
            <Background color="#BAEFE2" gap={20} size={1} />
            <Controls className="!bg-white !border-[#E1ECEE] !text-[#087F70] !fill-[#087F70] !shadow-sm !rounded-lg overflow-hidden" />
            <MiniMap
              className="!bg-white !border-[#E1ECEE] !rounded-lg !shadow-sm overflow-hidden"
              nodeColor={() => '#16B89A'}
              maskColor="rgba(245, 250, 250, 0.75)"
            />
          </ReactFlow>
        </div>

        {/* Node Detail Drawer */}
        {selectedNodeDetails && (
          <div className="w-80 border-l border-[#E1ECEE] bg-white p-5 flex flex-col justify-between overflow-y-auto shrink-0 z-20 shadow-card">
            <div>
              <div className="flex items-start justify-between pb-3 border-b border-[#E1ECEE] mb-3">
                <div>
                  <Badge variant="primary">{selectedNodeDetails.type}</Badge>
                  <h3 className="font-mono font-bold text-xs text-[#172B35] mt-1 break-all">
                    {selectedNodeDetails.name}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedNodeDetails(null)}
                  className="p-1 rounded text-[#6B818B] hover:text-[#172B35]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs font-mono">
                <div>
                  <div className="text-[#6B818B] uppercase text-[10px] font-bold">Source File</div>
                  <div className="text-[#172B35] break-all bg-[#F5FAFA] p-2 rounded border border-[#E1ECEE] mt-1">
                    {selectedNodeDetails.path}
                  </div>
                </div>

                {/* Callers */}
                <div>
                  <div className="text-[#6B818B] uppercase text-[10px] font-bold mb-1">
                    Incoming Callers ({selectedNodeDetails.incoming_callers?.length || 0})
                  </div>
                  {selectedNodeDetails.incoming_callers?.length > 0 ? (
                    <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                      {selectedNodeDetails.incoming_callers.map((c, i) => (
                        <div
                          key={i}
                          onClick={() => handleExpandNode(c.source)}
                          className="p-1.5 rounded bg-[#F5FAFA] border border-[#E1ECEE] hover:border-[#16B89A] hover:bg-[#DDF7EF]/40 cursor-pointer text-[11px] truncate text-[#172B35] transition-colors"
                        >
                          <div className="font-bold text-[#087F70]">{c.source.split('::').pop()}</div>
                          <div className="text-[9px] text-[#6B818B]">{c.relation_type}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[#6B818B] text-[11px] italic">No direct callers</div>
                  )}
                </div>

                {/* Dependencies */}
                <div>
                  <div className="text-[#6B818B] uppercase text-[10px] font-bold mb-1">
                    Outgoing Dependencies ({selectedNodeDetails.outgoing_dependencies?.length || 0})
                  </div>
                  {selectedNodeDetails.outgoing_dependencies?.length > 0 ? (
                    <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                      {selectedNodeDetails.outgoing_dependencies.map((d, i) => (
                        <div
                          key={i}
                          onClick={() => handleExpandNode(d.target)}
                          className="p-1.5 rounded bg-[#F5FAFA] border border-[#E1ECEE] hover:border-[#55BDEB] hover:bg-[#E2F4FC]/40 cursor-pointer text-[11px] truncate text-[#172B35] transition-colors"
                        >
                          <div className="font-bold text-[#258FC7]">{d.target.split('::').pop()}</div>
                          <div className="text-[9px] text-[#6B818B]">{d.relation_type}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[#6B818B] text-[11px] italic">No downstream calls</div>
                  )}
                </div>
              </div>
            </div>

            <button
              onClick={() => handleExpandNode(selectedNodeDetails.id)}
              className="w-full mt-4 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <span>Expand Neighborhood</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
